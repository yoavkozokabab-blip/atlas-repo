"""Desktop notifications with safe fallbacks."""

from __future__ import annotations

import re

from core.logger import setup_logger

logger = setup_logger("jarvis.ui.notify")

_MAX_MESSAGE = 240


def _sanitize_message(message: str) -> str:
    text = str(message or "").strip()
    text = re.sub(r"(api[_-]?key|token|password|secret)\s*[=:]\s*\S+", "[redacted]", text, flags=re.I)
    if len(text) > _MAX_MESSAGE:
        text = text[: _MAX_MESSAGE - 3] + "..."
    return text


def notify(title: str, message: str, *, icon: object | None = None) -> bool:
    """
    Show a notification. Returns True if a GUI notification was attempted successfully.
    Falls back to stdout on failure.
    """
    title = str(title or "JARVIS")[:64]
    message = _sanitize_message(message)
    if not message:
        message = "(no details)"

    if icon is not None:
        try:
            icon.notify(message, title)
            return True
        except Exception as exc:
            logger.debug("pystray notify failed: %s", exc)

    try:
        from win10toast import ToastNotifier

        ToastNotifier().show_toast(title, message, duration=5, threaded=True)
        return True
    except Exception as exc:
        logger.debug("win10toast failed: %s", exc)

    print(f"[{title}] {message}")
    return False
