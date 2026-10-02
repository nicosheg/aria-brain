import base64
import hashlib
import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet


class SecretBox:
    """Encrypt server-owned secrets and resumable agent state."""

    def __init__(self, configured_key: str = "", fallback_secret: str = ""):
        key = configured_key.strip()
        if not key:
            seed = (fallback_secret or "").encode("utf-8")
            if not seed:
                key_file = Path(os.getenv("ARIA_DATA_DIR", "/tmp/aria")) / ".dev-secret"
                key_file.parent.mkdir(parents=True, exist_ok=True)
                if key_file.exists():
                    seed = key_file.read_bytes()
                else:
                    seed = os.urandom(32)
                    key_file.write_bytes(seed)
            digest = hashlib.sha256(seed).digest()
            key = base64.urlsafe_b64encode(digest).decode("ascii")
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")


def normalize_identity(value: str) -> str:
    return (value or "").strip().lower()


def assert_public_http_url(url: str) -> str:
    """Validate an outbound HTTP(S) target and reject private-network destinations."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in URLs are not allowed.")

    hostname = parsed.hostname.rstrip(".").lower()
    blocked_names = {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.google.internal.",
        "metadata",
    }
    if hostname in blocked_names or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("Private or local network targets are blocked.")

    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(
                    hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            ]
        except OSError as exc:
            raise ValueError("The target host could not be resolved.") from exc

    if not addresses:
        raise ValueError("The target host has no resolved address.")

    for address in addresses:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ValueError("Private or local network targets are blocked.")

    return parsed.geturl()


def redact_secrets(text: str) -> str:
    """Best-effort redaction before user/tool data becomes durable or client-visible."""
    import re

    patterns = [
        r"(?i)\b(password|passwd|passcode|client_secret|secret)\s*[:=]\s*\S+",
        r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|auth[_ -]?token|authorization|token)\s*[:=]\s*[A-Za-z0-9_.\-/+=]{12,}",
        r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}\b",
        r"\bsk-[A-Za-z0-9_-]{16,}\b",
        r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b",
        r"\bAIza[0-9A-Za-z_-]{20,}\b",
    ]
    redacted = text or ""
    for pattern in patterns:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted
