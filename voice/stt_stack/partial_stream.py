"""Partial transcript streaming to overlay / debug."""

from __future__ import annotations

from typing import Callable

from config import STT_PARTIAL_STREAMING_ENABLED
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stt.partial")

PartialCallback = Callable[[str], None]
_listeners: list[PartialCallback] = []
_last_partial: str = ""


def register_partial_listener(cb: PartialCallback) -> None:
    if cb not in _listeners:
        _listeners.append(cb)


def clear_partial_listeners() -> None:
    _listeners.clear()


def get_last_partial() -> str:
    return _last_partial


def emit_partial(text: str) -> None:
    global _last_partial
    if not STT_PARTIAL_STREAMING_ENABLED:
        return
    chunk = (text or "").strip()
    if not chunk or chunk == _last_partial:
        return
    _last_partial = chunk
    try:
        from core.event_bus import get_event_bus

        get_event_bus().publish_nowait("stt.partial", text=chunk)
    except Exception:
        pass
    for cb in list(_listeners):
        try:
            cb(chunk)
        except Exception as exc:
            logger.debug("partial listener: %s", exc)
    try:
        from ui.overlay_app import notify_overlay_partial_transcript

        notify_overlay_partial_transcript(chunk)
    except Exception:
        pass


def make_partial_callback() -> PartialCallback:
    return emit_partial
