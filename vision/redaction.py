"""Redact sensitive text from OCR / screen summaries."""

from __future__ import annotations

import re

from brain.storage_safe import (
    CREDIT_CARD,
    ENV_LINE,
    LONG_BASE64,
    SECRET_PATTERNS,
)
from config import VISION_REDACT_SENSITIVE_TEXT

_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b", re.I)
_AUTH_HEADER = re.compile(r"Authorization:\s*\S+", re.I)


def redact_sensitive_text(text: str) -> str:
    """Remove or mask patterns that may contain secrets."""
    if not text or not VISION_REDACT_SENSITIVE_TEXT:
        return text

    out = str(text)
    for pat in SECRET_PATTERNS:
        out = pat.sub("[redacted]", out)
    out = _BEARER.sub("Bearer [redacted]", out)
    out = _AUTH_HEADER.sub("Authorization: [redacted]", out)
    out = _EMAIL.sub("[email redacted]", out)
    out = CREDIT_CARD.sub("[card redacted]", out)
    out = LONG_BASE64.sub("[encoded redacted]", out)

    lines: list[str] = []
    for line in out.splitlines():
        if ENV_LINE.match(line.strip()):
            lines.append("[env line redacted]")
        else:
            lines.append(line)
    return "\n".join(lines)
