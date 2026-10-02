from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|passcode)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(api[_ -]?key|secret|token|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*[:=]\s*[A-Za-z0-9_\-./+=]{8,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"),
)


def redact_secrets(text: str | None) -> str:
    value = text or ""
    for pattern in _SECRET_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            if match.lastindex:
                return f"{match.group(1)}: [REDACTED]"
            return "[REDACTED]"
        value = pattern.sub(replace, value)
    return value
