from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|passcode)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_ -]?key|secret|token|access[_ -]?token|refresh[_ -]?token)\s*[:=]\s*[A-Za-z0-9_\-./+=]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"),
)


def redact_secrets(text: str | None) -> str:
    value = text or ""
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(lambda m: f"{m.group(1)}: [REDACTED]" if m.groups() else "[REDACTED]", value)
    return value
