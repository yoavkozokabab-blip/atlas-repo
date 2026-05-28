"""Continuous streaming microphone — rolling VAD without fixed wake windows (Phase 59)."""

from __future__ import annotations

import threading
import time
from typing import Callable

from core.logger import setup_logger
from voice.streaming_stt.stream_session import StreamingSttResult, StreamingSttSession, is_streaming_stt_enabled

logger = setup_logger("jarvis.voice.continuous_mic")

_streaming_active = False
_streaming_lock = threading.Lock()
_streaming_thread: threading.Thread | None = None


def _partial_interval_ms() -> float:
    try:
        import config as cfg

        return float(getattr(cfg, "CONVERSATION_PARTIAL_INTERVAL_MS", 150.0))
    except Exception:
        return 150.0


def _turn_max_seconds() -> float:
    try:
        import config as cfg

        raw = float(getattr(cfg, "CONVERSATION_TURN_MAX_SECONDS", 45.0))
        return max(8.0, raw)
    except Exception:
        return 45.0


def _session_max_seconds() -> float:
    try:
        import config as cfg

        raw = float(getattr(cfg, "CONVERSATION_SESSION_MAX_SECONDS", 600.0))
        return max(30.0, raw)
    except Exception:
        return 600.0


def _session_idle_seconds() -> float:
    try:
        import config as cfg

        raw = float(getattr(cfg, "CONVERSATION_SESSION_IDLE_SECONDS", 60.0))
        return max(2.0, min(raw, 120.0))
    except Exception:
        return 60.0


def is_streaming_session_active() -> bool:
    with _streaming_lock:
        return _streaming_active


def capture_turn(
    *,
    session_context: object | None = None,
    on_partial: Callable[[str], None] | None = None,
    audio_feed: Callable | None = None,
) -> StreamingSttResult:
    """Capture one conversational turn using endpointing (no fixed 5s wake cap)."""
    if not is_streaming_stt_enabled():
        return StreamingSttResult(
            text="",
            partial_updates=0,
            decode_ms=0.0,
            record_seconds=0.0,
            endpoint_silence_ms=0.0,
        )
    session = StreamingSttSession(
        session_context=session_context,
        partial_interval_ms=_partial_interval_ms(),
        audio_feed=audio_feed,
        on_partial=on_partial,
    )
    max_attempts = 1 + max(0, int(getattr(__import__("config"), "STT_STREAM_PARTIAL_RETRY_COUNT", 2)))
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            t0 = time.perf_counter()
            result = session.run_until_endpoint(max_seconds=_turn_max_seconds())
            if on_partial and result.partial_updates == 0 and result.text:
                on_partial(result.text)
            logger.info(
                "continuous_mic turn text=%r partials=%s seconds=%.1f",
                (result.text or "")[:80],
                result.partial_updates,
                time.perf_counter() - t0,
            )
            return result
        except Exception as exc:
            from voice.streaming_stt.session_policy import (
                StreamingSttFallbackError,
                audio_flowing_for_session,
                is_streaming_stt_enabled_for_session,
            )

            last_exc = exc
            if isinstance(exc, StreamingSttFallbackError) and (
                attempt + 1 < max_attempts and is_streaming_stt_enabled_for_session()
            ):
                logger.warning(
                    "continuous_mic turn retry %s/%s after partial failure",
                    attempt + 1,
                    max_attempts,
                )
                session = StreamingSttSession(
                    session_context=session_context,
                    partial_interval_ms=_partial_interval_ms(),
                    audio_feed=audio_feed,
                    on_partial=on_partial,
                )
                continue
            if isinstance(exc, StreamingSttFallbackError) and audio_flowing_for_session():
                logger.warning(
                    "continuous_mic turn soft-fail (session continues): %s",
                    exc,
                )
                return StreamingSttResult(
                    text="",
                    partial_updates=0,
                    decode_ms=0.0,
                    record_seconds=0.0,
                    endpoint_silence_ms=0.0,
                )
            raise
    if last_exc is not None:
        raise last_exc
    return StreamingSttResult(
        text="",
        partial_updates=0,
        decode_ms=0.0,
        record_seconds=0.0,
        endpoint_silence_ms=0.0,
    )


def run_continuous_mic_session(
    *,
    session_context: object | None = None,
    on_partial: Callable[[str], None] | None = None,
    on_turn: Callable[[str], bool] | None = None,
    on_idle_timeout: Callable[[], None] | None = None,
    audio_feed: Callable | None = None,
) -> dict[str, object]:
    """
    Run rolling mic session until idle timeout or on_turn returns False.
    Each turn ends on VAD endpoint, not a fixed wake window.
    """
    from assistant.conversation_state import set_continuous_listening
    from conversation.conversation_metrics import begin_conversation_turn, record_conversation_turn
    from voice.streaming_pipeline import get_streaming_pipeline

    global _streaming_active
    with _streaming_lock:
        _streaming_active = True

    set_continuous_listening(True)
    pipeline = get_streaming_pipeline(session_context=session_context)
    pipeline.start()
    session_deadline = time.monotonic() + _session_max_seconds()
    idle_seconds = _session_idle_seconds()
    last_activity = time.monotonic()
    turns = 0
    partials = 0
    last_text = ""
    try:
        while time.monotonic() < session_deadline:
            if time.monotonic() - last_activity >= idle_seconds:
                logger.info("continuous_mic idle timeout after %.1fs silence", idle_seconds)
                if on_idle_timeout:
                    on_idle_timeout()
                break

            metrics = begin_conversation_turn(turn_id=turns + 1)

            def _partial_hook(text: str) -> None:
                nonlocal partials, last_activity
                partials += 1
                last_activity = time.monotonic()
                metrics.mark_first_partial_stt()
                pipeline.push_partial(text)
                if on_partial:
                    on_partial(text)
                try:
                    from voice.streaming_player import is_speaking
                    from voice.human_interruption import on_user_speech_during_tts

                    if text.strip() and is_speaking():
                        on_user_speech_during_tts(partial_text=text)
                except Exception:
                    pass

            turn = capture_turn(
                session_context=session_context,
                on_partial=_partial_hook,
                audio_feed=audio_feed,
            )
            record_conversation_turn(metrics)
            text = (turn.text or "").strip()
            last_text = text
            turns += 1
            if text:
                last_activity = time.monotonic()
                keep_going = True
                if on_turn:
                    keep_going = bool(on_turn(text))
                if not keep_going:
                    break
    finally:
        with _streaming_lock:
            _streaming_active = False
        set_continuous_listening(False)

    elapsed = _session_max_seconds() - max(0.0, session_deadline - time.monotonic())
    return {
        "turns": turns,
        "partials": partials,
        "responses": pipeline.metrics.responses,
        "last_text": last_text,
        "session_seconds": round(elapsed, 1),
        "idle_timeout_seconds": idle_seconds,
    }


def start_streaming_session(
    *,
    session_context: object | None = None,
    on_partial: Callable[[str], None] | None = None,
    on_turn: Callable[[str], bool] | None = None,
    on_finished: Callable[[dict[str, object]], None] | None = None,
    audio_feed: Callable | None = None,
) -> threading.Thread:
    """Start continuous mic session on a background thread."""
    global _streaming_thread

    def _runner() -> None:
        result = run_continuous_mic_session(
            session_context=session_context,
            on_partial=on_partial,
            on_turn=on_turn,
            audio_feed=audio_feed,
        )
        if on_finished:
            on_finished(result)

    with _streaming_lock:
        if _streaming_thread and _streaming_thread.is_alive():
            return _streaming_thread
        _streaming_thread = threading.Thread(
            target=_runner,
            name="jarvis-continuous-mic",
            daemon=True,
        )
        _streaming_thread.start()
        return _streaming_thread


def reset_continuous_mic_for_tests() -> None:
    global _streaming_active, _streaming_thread
    with _streaming_lock:
        _streaming_active = False
        _streaming_thread = None
