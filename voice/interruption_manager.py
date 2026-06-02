"""Natural barge-in and interrupted-response recovery (Phase 56)."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.interruption_manager")

_lock = threading.RLock()
_speaking_text: str = ""
_interrupted: bool = False
_last_event: str = "idle"


@dataclass(frozen=True)
class InterruptionResult:
    stopped_tts: bool
    preserved_response: bool
    state: str
    resume_available: bool


def cancel(*, partial_text: str = "") -> bool:
    """Instant cancel for active TTS stream + playback."""
    del partial_text
    try:
        from voice.realtime_tts import cancel_active_speech

        return cancel_active_speech()
    except Exception:
        try:
            from voice.streaming_player import is_speaking, request_stop_speaking

            request_stop_speaking()
            return is_speaking()
        except Exception:
            return False


def on_user_speech_detected(
    *,
    partial_text: str = "",
    preserve_response: bool = True,
    playback_already_stopped: bool = False,
) -> InterruptionResult:
    """
    Stop TTS immediately when user starts speaking; preserve unfinished response.
    """
    global _interrupted, _last_event
    stopped = bool(playback_already_stopped)
    preserved = False
    with _lock:
        speaking = _speaking_text
        if not playback_already_stopped:
            try:
                from voice.duplex_runtime import on_user_speech_energy_detected

                on_user_speech_energy_detected(partial_text=partial_text)
            except Exception:
                pass
            try:
                from conversation.semantic_stream.interruption_handler import (
                    handle_streaming_interruption,
                )

                event = handle_streaming_interruption(speech_detected=True)
                stopped = event.barge_in_triggered
            except Exception:
                stopped = cancel()
        if not stopped and not playback_already_stopped:
            try:
                from voice.speech_controller import barge_in_if_speaking

                stopped = barge_in_if_speaking()
            except Exception:
                stopped = False
        if preserve_response and speaking and stopped:
            try:
                from assistant.conversation_state import store_paused_response

                store_paused_response(speaking)
                preserved = True
            except Exception:
                pass
        if stopped:
            _interrupted = True
            _last_event = "user_barge_in"
            try:
                from assistant.conversation_state import set_interruption_state

                set_interruption_state("user_barge_in")
            except Exception:
                pass
            logger.info("Barge-in: stopped TTS (partial=%r)", (partial_text or "")[:60])
    resume = preserved or bool(speaking)
    return InterruptionResult(
        stopped_tts=stopped,
        preserved_response=preserved,
        state=_last_event,
        resume_available=resume,
    )


def on_jarvis_speech_started(text: str) -> None:
    global _speaking_text, _interrupted, _last_event
    with _lock:
        _speaking_text = (text or "")[:1200]
        _interrupted = False
        _last_event = "speaking"
        try:
            from assistant.conversation_state import set_interruption_state

            set_interruption_state("speaking")
        except Exception:
            pass


def on_jarvis_speech_finished(*, interrupted: bool = False) -> None:
    global _speaking_text, _interrupted, _last_event
    with _lock:
        if interrupted:
            _interrupted = True
            _last_event = "interrupted"
        else:
            _speaking_text = ""
            _interrupted = False
            _last_event = "idle"
        try:
            from assistant.conversation_state import set_interruption_state

            set_interruption_state(_last_event)
        except Exception:
            pass


def resume_interrupted_response() -> str:
    global _speaking_text, _interrupted, _last_event
    with _lock:
        try:
            from assistant.conversation_state import clear_paused_response

            paused = clear_paused_response()
        except Exception:
            paused = _speaking_text
        _interrupted = False
        _last_event = "idle"
        _speaking_text = ""
    return paused or ""


def get_interruption_snapshot() -> dict[str, object]:
    with _lock:
        try:
            from assistant.conversation_state import show_conversation_state

            state_text = show_conversation_state()
            paused_len = 0
            if "paused response chars:" in state_text:
                for line in state_text.splitlines():
                    if "paused response chars:" in line:
                        try:
                            paused_len = int(line.split(":")[-1].strip())
                        except ValueError:
                            paused_len = 0
        except Exception:
            paused_len = 0
        return {
            "state": _last_event,
            "interrupted": _interrupted,
            "speaking_chars": len(_speaking_text),
            "paused_response_chars": paused_len,
        }


def reset_interruption_manager_for_tests() -> None:
    global _speaking_text, _interrupted, _last_event
    with _lock:
        _speaking_text = ""
        _interrupted = False
        _last_event = "idle"
