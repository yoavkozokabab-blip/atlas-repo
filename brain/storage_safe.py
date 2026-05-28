"""Shared validation — block secrets in local storage."""

from __future__ import annotations

import re

SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(api[_-]?key|token|password|secret|bearer)\s*[=:]\s*\S+", re.I),
    re.compile(r"(OPENAI|TELEGRAM|AWS|AZURE|GITHUB)[_A-Z]*\s*[=:]\s*\S+", re.I),
    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", re.I),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]
ENV_LINE = re.compile(r"^[A-Z][A-Z0-9_]{2,}=[^\s]+$", re.MULTILINE)
CREDIT_CARD = re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")
LONG_BASE64 = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")
FORBIDDEN_ALIAS_SUBSTRINGS = frozenset(
    {
        "powershell",
        "cmd.exe",
        "rm -rf",
        "del /f",
        "invoke-expression",
        "eval(",
        "exec(",
        "__import__",
    }
)


class UnsafeStorageError(Exception):
    """Value must not be stored locally."""


def validate_safe_value(key: str, value: str, *, field: str = "value") -> None:
    """Raise UnsafeStorageError if key/value looks like a secret or dangerous content."""
    combined = f"{key} {value}"
    for pat in SECRET_PATTERNS:
        if pat.search(combined):
            raise UnsafeStorageError(
                f"{field} appears to contain secrets. Do not store API keys, tokens, or passwords in memory."
            )
    for line in str(value).splitlines():
        if ENV_LINE.match(line.strip()):
            raise UnsafeStorageError(
                f"{field} looks like an environment line. Store only non-secret preferences."
            )
    if CREDIT_CARD.search(str(value)):
        raise UnsafeStorageError(f"{field} looks like payment card data.")
    if LONG_BASE64.search(str(value)) and len(value) > 60:
        raise UnsafeStorageError(f"{field} looks like encoded secret material.")

    lower = str(value).lower()
    for bad in FORBIDDEN_ALIAS_SUBSTRINGS:
        if bad in lower:
            raise UnsafeStorageError(f"{field} contains disallowed command-like content.")


def validate_safe_key(key: str) -> None:
    if not key or not str(key).strip():
        raise UnsafeStorageError("Key cannot be empty.")
    if len(key) > 120:
        raise UnsafeStorageError("Key is too long.")
    validate_safe_value(key, key, field="key")
