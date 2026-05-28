"""Human interruption model — sub-100ms pause with state preservation (Phase 59)."""

from __future__ import annotations

import threading
import time

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.human_interruption")

_lock = threading.RLock()
_interruption_active = False
_last_pause_ms: float | None = None
_preserved_text: str = ""
_resume_pending = False


def on_user_speech_during_tts(*, partial_text: str = "") -> bool:
    """Pause playback immediately; preserve assistant response state."""
    global _interruption_active, _last_pause_ms, _resume_pending
    t0 = time.perf_counter()
    paused = False
    with _lock:
        try:
            from voice.duplex_runtime import on_user_speech_energy_detected

            on_user_speech_energy_detected(partial_text=partial_text)
            paused = True
        except Exception:
            pass
        if not paused:
            try:
                from voice.streaming_player import pause_playback_immediately

                pause_playback_immediately()
                paused = True
            except Exception:
                pass
        try:
            from voice.interruption_manager import on_user_speech_detected

            result = on_user_speech_detected(partial_text=partial_text, preserve_response=True)
            paused = paused or result.stopped_tts
        except Exception:
            pass
        pause_ms = (time.perf_counter() - t0) * 1000.0
        _last_pause_ms = pause_ms
        _interruption_active = True
        _resume_pending = True
        try:
            from conversation.conversation_metrics import get_last_conversation_metrics

            rec = get_last_conversation_metrics()
            if rec is not None:
                rec.mark_interrupt_pause(pause_ms)
        except Exception:
            pass
        try:
            from conversation.memory_runtime import record_interruption_event

            record_interruption_event(partial_text=partial_text)
        except Exception:
            pass
        logger.debug("Human interruption pause_ms=%.1f partial=%r", pause_ms, partial_text[:40])
    try:
        from voice.tts_output_policy import notify_overlay_interrupted

        notify_overlay_interrupted()
    except Exception:
        pass
    return paused


def resume_if_interruption_ended(*, speak: bool = True) -> str:
    """Resume naturally when user stops speaking."""
    global _interruption_active, _resume_pending
    with _lock:
        if not _resume_pending:
            return ""
        _resume_pending = False
        _interruption_active = False
        try:
            from voice.interruption_manager import resume_interrupted_response

            paused = resume_interrupted_response()
        except Exception:
            paused = _preserved_text
        try:
            from conversation.conversation_metrics import get_last_conversation_metrics

            rec = get_last_conversation_metrics()
            if rec is not None:
                rec.mark_resumed()
        except Exception:
            pass
        if speak and paused.strip():
            try:
                from voice.realtime_tts import speak_realtime

                speak_realtime(paused.strip())
            except Exception as exc:
                logger.debug("Resume speak failed: %s", exc)
        return paused or ""


def get_human_interruption_snapshot() -> dict[str, object]:
    with _lock:
        return {
            "active": _interruption_active,
            "last_pause_ms": _last_pause_ms,
            "resume_pending": _resume_pending,
        }


def reset_human_interruption_for_tests() -> None:
    global _interruption_active, _last_pause_ms, _preserved_text, _resume_pending
    with _lock:
        _interruption_active = False
        _last_pause_ms = None
        _preserved_text = ""
        _resume_pending = False
