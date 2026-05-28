"""Phase 35 — screen text redaction before any user-facing output."""

from __future__ import annotations

import re

from config import SCREEN_REDACTION_ENABLED

_SECRET_KEY = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|credential|private\s*key|bearer)"
)
_ENV_ASSIGN = re.compile(
    r"^([A-Za-z][A-Za-z0-9_]*(?:key|token|secret|password|credential)[A-Za-z0-9_]*)=(.+)$",
    re.MULTILINE,
)
_ASSIGN_SECRET = re.compile(
    r"(?i)\b(password|token|api[_-]?key|secret|credential|private\s*key)\s*=\s*\S+"
)
_BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._\-+/=]+")
_SK_KEY = re.compile(r"\bsk(?:-[A-Za-z0-9]+)?-[A-Za-z0-9]{12,}\b", re.I)
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_LONG_B64 = re.compile(r"\b[A-Za-z0-9+/]{60,}={0,2}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_screen_text(text: str, *, max_len: int | None = None) -> str:
    if not text:
        return ""
    if not SCREEN_REDACTION_ENABLED:
        out = text
    else:
        out = str(text)
        out = _ASSIGN_SECRET.sub(
            lambda m: f"{m.group(1)}=[REDACTED]",
            out,
        )
        out = _SECRET_KEY.sub("[REDACTED]", out)
        out = _BEARER.sub("Bearer [REDACTED]", out)
        out = _SK_KEY.sub("sk-[REDACTED]", out)
        out = _LONG_HEX.sub("[hex redacted]", out)
        out = _LONG_B64.sub("[encoded redacted]", out)
        out = _EMAIL.sub("[email redacted]", out)

        lines: list[str] = []
        for line in out.splitlines():
            m = _ENV_ASSIGN.match(line.strip())
            if m:
                lines.append(f"{m.group(1)}=[REDACTED]")
            elif re.match(r"^[A-Z][A-Z0-9_]{2,}=", line.strip()):
                key = line.split("=", 1)[0]
                if any(
                    s in key.lower()
                    for s in ("key", "token", "secret", "password", "credential")
                ):
                    lines.append(f"{key}=[REDACTED]")
                else:
                    lines.append(line)
            else:
                lines.append(line)
        out = "\n".join(lines)

    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if max_len and len(out) > max_len:
        out = out[: max_len - 3] + "..."
    return out
