import base64
import hashlib
import os
from pathlib import Path

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


def redact_secrets(text: str) -> str:
    """Best-effort redaction before user text becomes durable memory."""
    import re

    patterns = [
        r"(?i)(password|passwd|passcode)\s*[:=]\s*\S+",
        r"(?i)(api[_ -]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_\-./+=]{12,}",
        r"\bsk-[A-Za-z0-9_-]{16,}\b",
        r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b",
    ]
    redacted = text or ""
    for pattern in patterns:
        def replacement(match):
            groups = match.groups()
            return f"{groups[0]}: [REDACTED]" if groups else "[REDACTED]"
        redacted = re.sub(pattern, replacement, redacted)
    return redacted
