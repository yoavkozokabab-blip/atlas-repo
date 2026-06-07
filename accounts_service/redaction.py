"""Redact sensitive content before persisting user feedback."""
from __future__ import annotations

import re
from typing import Optional

_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)


def redact_feedback_message(message: str, *, contact_email: Optional[str] = None) -> str:
    """Strip secrets, paths, and incidental emails from free-text feedback."""
    if not message:
        return ""
    out = message
    out = re.sub(r"[A-Za-z]:\\(?:[^\"\\\s]|\\.)+", "[path-redacted]", out)
    out = re.sub(r"/(?:home|Users|var|tmp|opt)/(?:[^\"\\\s]|\\.)+", "[path-redacted]", out)
    out = re.sub(r"(?i)\bapi_key\s*[=:]\s*\S+", "api_key=[REDACTED]", out)
    out = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", out)
    out = re.sub(r"(?i)\bAuthorization:\s*\S+", "Authorization: [REDACTED]", out)
    out = re.sub(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*", "[REDACTED]", out)
    out = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "[REDACTED]", out)
    out = re.sub(r"\bsk-[A-Za-z0-9_\-]{8,}", "[REDACTED]", out)
    out = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", out)
    out = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED]", out)

    preserve = (contact_email or "").strip().lower()

    def _email_sub(match: re.Match[str]) -> str:
        found = match.group(0)
        if preserve and found.lower() == preserve:
            return found
        return "[email-redacted]"

    out = _EMAIL_RE.sub(_email_sub, out)
    return out.strip()[:2000]
