"""Safety gates for computer control (no free automation)."""

from __future__ import annotations

import re

from brain.storage_safe import UnsafeStorageError, validate_safe_value
from config import CLIPBOARD_MAX_CHARS, COMPUTER_CONTROL_DISABLED_MESSAGE
from vision.redaction import redact_sensitive_text

# Titles we must never focus/minimize/maximize
SENSITIVE_TITLE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"password", re.I),
    re.compile(r"credential", re.I),
    re.compile(r"bitlocker", re.I),
    re.compile(r"1password|lastpass|keepass|dashlane", re.I),
    re.compile(r"\b(sign[\s-]?in|log[\s-]?in)\b", re.I),
    re.compile(r"authenticator", re.I),
    re.compile(r"private[\s-]?key", re.I),
    re.compile(r"wallet", re.I),
]

SYSTEM_OR_HIDDEN_TITLES: frozenset[str] = frozenset(
    {
        "",
        "program manager",
        "msctfime ui",
        "default ime",
        "windows input experience",
    }
)

MIN_WINDOW_SIZE = 50


class ComputerControlDisabledError(Exception):
    pass


class ComputerControlSafetyError(Exception):
    pass


def ensure_control_enabled() -> None:
    from config import COMPUTER_CONTROL_ENABLED

    if not COMPUTER_CONTROL_ENABLED:
        raise ComputerControlDisabledError(COMPUTER_CONTROL_DISABLED_MESSAGE)


def is_sensitive_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    for pat in SENSITIVE_TITLE_PATTERNS:
        if pat.search(t):
            return True
    return False


def is_system_or_hidden_title(title: str) -> bool:
    norm = (title or "").strip().lower()
    if norm in SYSTEM_OR_HIDDEN_TITLES:
        return True
    if norm.startswith("msctfime"):
        return True
    return False


def is_eligible_window(title: str, width: int, height: int, *, minimized: bool = False) -> tuple[bool, str | None]:
    """Whether a window may be listed or targeted (read-only list may show ineligible)."""
    if is_system_or_hidden_title(title):
        return False, "system or hidden window"
    if is_sensitive_title(title):
        return False, "sensitive window title"
    if width < MIN_WINDOW_SIZE and height < MIN_WINDOW_SIZE and not minimized:
        return False, "zero-size or hidden window"
    if not (title or "").strip():
        return False, "empty title"
    return True, None


def validate_clipboard_write(text: str) -> None:
    """Block copying secrets to clipboard."""
    if not text or not str(text).strip():
        raise ComputerControlSafetyError("Clipboard text cannot be empty.")
    if len(text) > CLIPBOARD_MAX_CHARS:
        raise ComputerControlSafetyError(
            f"Text exceeds CLIPBOARD_MAX_CHARS ({CLIPBOARD_MAX_CHARS})."
        )
    try:
        validate_safe_value("clipboard", text, field="clipboard text")
    except UnsafeStorageError as exc:
        raise ComputerControlSafetyError(str(exc)) from exc


def summarize_clipboard_text(raw: str) -> tuple[str, bool]:
    """Redact and cap clipboard readback."""
    text = redact_sensitive_text(raw or "")
    truncated = False
    if len(text) > CLIPBOARD_MAX_CHARS:
        text = text[: CLIPBOARD_MAX_CHARS - 3] + "..."
        truncated = True
    return text, truncated
