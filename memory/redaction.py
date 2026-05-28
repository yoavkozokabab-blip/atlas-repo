"""Redact secrets before storing or displaying knowledge."""

from __future__ import annotations

import re

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)(OPENAI|TELEGRAM|AWS|AZURE|GITHUB)[_A-Z]*\s*[=:]\s*\S+"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
]

_ENV_LINE = re.compile(r"^[A-Z][A-Z0-9_]{2,}=[^\s#]+$", re.MULTILINE)


class UnsafeMemoryError(Exception):
    """Content must not be stored in the knowledge base."""


def redact_text(text: str, *, max_len: int = 2000) -> str:
    if not text:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    for line in out.splitlines():
        if _ENV_LINE.match(line.strip()):
            out = out.replace(line, "***REDACTED***")
    if len(out) > max_len:
        out = out[:max_len] + "…"
    return out


def validate_safe_text(text: str) -> None:
    """Raise if text must not be stored."""
    raw = text or ""
    for pat in _SECRET_PATTERNS:
        if pat.search(raw):
            raise UnsafeMemoryError(
                "Text appears to contain secrets. Do not store API keys, tokens, or passwords."
            )
    for line in raw.splitlines():
        if _ENV_LINE.match(line.strip()):
            raise UnsafeMemoryError("Text looks like a raw .env line. Store summaries only.")


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
    seen: set[str] = set()
    out: list[str] = []
    stop = {"the", "and", "for", "that", "this", "with", "from", "are", "was"}
    for w in words:
        if w in stop or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= limit:
            break
    return out
