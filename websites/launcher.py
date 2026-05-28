"""Open allowlisted websites via webbrowser.open() only."""

from __future__ import annotations

import webbrowser

from core.logger import setup_logger
from websites.registry import WebsiteEntry
from websites.safety import SafetyError, validate_url

logger = setup_logger("jarvis.websites.launcher")


def _notify_opening(display_name: str) -> None:
    try:
        from ui.overlay_app import update_overlay_state

        update_overlay_state("thinking", f"Opening {display_name}...")
    except Exception:
        pass


def _notify_opened(display_name: str) -> None:
    try:
        from ui.overlay_app import update_overlay_state

        update_overlay_state("done", f"Opened {display_name}")
    except Exception:
        pass


def launch_website(entry: WebsiteEntry) -> str:
    """
    Open URL in default browser using webbrowser.open() only.
    Never shell=True, no browser CLI args, no automation.
    """
    url = validate_url(entry.url)
    _notify_opening(entry.display_name)
    try:
        ok = bool(webbrowser.open(url, new=2))
    except OSError as exc:
        raise SafetyError(f"Could not open browser: {exc}") from exc
    if not ok:
        raise SafetyError("Browser did not accept the URL.")
    logger.info("Opened website %s (%s)", entry.display_name, url)
    _notify_opened(entry.display_name)
    return f"Opened {entry.display_name}."
