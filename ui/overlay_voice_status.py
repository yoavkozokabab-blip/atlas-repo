"""Overlay voice output status — SPEAKING / TTS BLOCKED / MUTED / etc. (Phase 59.2)."""

from __future__ import annotations

from core.logger import setup_logger

logger = setup_logger("jarvis.ui.overlay_voice_status")

_last_status = ""


def notify_overlay_voice_output_status(status: str, *, detail: str = "") -> None:
    global _last_status
    status = (status or "").strip().upper()
    if not status:
        return
    _last_status = status
    try:
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()

        def _apply() -> None:
            ctrl._state.set_voice_output_status(status, detail=detail)

        ctrl._apply_if_active(_apply)
    except Exception as exc:
        logger.debug("overlay voice status: %s", exc)


def get_last_overlay_voice_status() -> str:
    return _last_status


def reset_overlay_voice_status_for_tests() -> None:
    global _last_status
    _last_status = ""
