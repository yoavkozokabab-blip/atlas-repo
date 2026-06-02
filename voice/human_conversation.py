"""Human conversation runtime — fast barge-in and unified interrupt entry (Voice-Hardening)."""

from __future__ import annotations

import threading
import time
from typing import Callable

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.human_conversation")

_last_cancel_ms: float | None = None
_barge_in_lock = threading.Lock()
_barge_in_active = False


def is_barge_in_active() -> bool:
    with _barge_in_lock:
        return _barge_in_active


def _halt_active_playback() -> bool:
    """Synchronous cancel — playback stop before provider/stream cleanup."""
    stopped = False
    try:
        from voice.streaming_player import (
            is_speaking,
            pause_playback_immediately,
            request_stop_speaking,
        )

        pause_playback_immediately()
        request_stop_speaking()
    except Exception:
        pass
    try:
        from voice.realtime_tts import cancel_active_speech

        stopped = bool(cancel_active_speech())
    except Exception:
        pass
    if not stopped:
        try:
            from voice.streaming_player import is_speaking

            stopped = bool(is_speaking())
        except Exception:
            pass
    return stopped


def _notify_interruption_deferred(*, partial_text: str) -> None:
    try:
        from voice.human_interruption import on_user_speech_during_tts

        on_user_speech_during_tts(
            partial_text=partial_text,
            playback_already_stopped=True,
        )
    except Exception:
        try:
            from voice.interruption_manager import on_user_speech_detected

            on_user_speech_detected(
                partial_text=partial_text,
                preserve_response=True,
                playback_already_stopped=True,
            )
        except Exception:
            pass


def interrupt_on_user_speech_start(*, partial_text: str = "") -> bool:
    """
    Stop JARVIS speech immediately when user starts talking.

    Targets sub-200ms cancel by pausing playback and cancelling the active
    provider stream before higher-level recovery hooks run (deferred).
    """
    global _last_cancel_ms, _barge_in_active
    with _barge_in_lock:
        if _barge_in_active:
            return True
        _barge_in_active = True
    t0 = time.perf_counter()
    stopped = False
    try:
        stopped = _halt_active_playback()
    finally:
        with _barge_in_lock:
            _barge_in_active = False
    _last_cancel_ms = (time.perf_counter() - t0) * 1000.0
    try:
        import config as cfg

        target = float(getattr(cfg, "HUMAN_BARGE_IN_TARGET_MS", 200.0))
        if _last_cancel_ms > target:
            logger.warning(
                "Barge-in cancel_ms=%.1f exceeded target %.0fms",
                _last_cancel_ms,
                target,
            )
    except Exception:
        pass
    logger.debug(
        "interrupt_on_user_speech_start cancel_ms=%.1f stopped=%s partial=%r",
        _last_cancel_ms,
        stopped,
        (partial_text or "")[:40],
    )
    threading.Thread(
        target=_notify_interruption_deferred,
        kwargs={"partial_text": partial_text},
        daemon=True,
        name="jarvis-barge-in-notify",
    ).start()
    return stopped


def get_last_barge_in_cancel_ms() -> float | None:
    return _last_cancel_ms


def reset_human_conversation_for_tests() -> None:
    global _last_cancel_ms, _barge_in_active
    _last_cancel_ms = None
    with _barge_in_lock:
        _barge_in_active = False
