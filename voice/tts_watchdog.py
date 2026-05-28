"""Hard SPEAK watchdog — kill stuck TTS subprocess and clear overlay."""

from __future__ import annotations

import threading
import time
from typing import Any

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts.watchdog")

_lock = threading.RLock()
_active_proc: Any = None
_active_pid: int | None = None
_speak_started_at: float | None = None
_speak_started_wall: float | None = None
_speak_session_id: int = 0
_watchdog_timer: threading.Timer | None = None
_last_kill_reason: str | None = None


def get_speak_max_seconds() -> float:
    try:
        import config as cfg

        raw = float(getattr(cfg, "TTS_SPEAK_MAX_SECONDS", 8.0))
        return max(1.0, min(8.0, raw))
    except Exception:
        return 8.0


def get_speak_timeout_seconds(text: str = "", *, rate_raw: str = "") -> float:
    """Resolve outer TTS timeout; direct pyttsx3 needs room for grace recovery."""
    base = get_speak_max_seconds()
    if not (text or "").strip():
        return base
    try:
        from voice.pyttsx3_completion import (
            completion_grace_recovery_enabled,
            get_direct_completion_timeout_seconds,
        )

        if completion_grace_recovery_enabled():
            return max(base, min(get_direct_completion_timeout_seconds(text, rate_raw), 45.0))
        from voice.pyttsx3_completion import estimate_speech_duration_seconds

        estimated = estimate_speech_duration_seconds(text, rate_raw)
        return max(base, min(estimated + 3.0, 25.0))
    except Exception:
        return base


_pending_speak_timeout: float | None = None


def set_pending_speak_timeout(seconds: float) -> None:
    global _pending_speak_timeout
    _pending_speak_timeout = max(1.0, float(seconds))


def _resolve_watchdog_seconds() -> float:
    pending = _pending_speak_timeout
    if pending is not None:
        return pending
    return get_speak_max_seconds()


def get_subprocess_timeout_seconds() -> float:
    """Hard cap for Popen communicate (never above SPEAK max)."""
    try:
        import config as cfg

        configured = float(getattr(cfg, "TTS_TIMEOUT_SECONDS", 8.0))
    except Exception:
        configured = 8.0
    return min(get_speak_max_seconds(), configured)


def get_active_tts_pid() -> int | None:
    with _lock:
        return _active_pid


def get_speak_started_at() -> float | None:
    with _lock:
        return _speak_started_wall


def get_speak_elapsed_ms() -> float | None:
    with _lock:
        if _speak_started_at is None:
            return None
        return (time.monotonic() - _speak_started_at) * 1000.0


def get_last_kill_reason() -> str | None:
    with _lock:
        return _last_kill_reason


def is_speak_active() -> bool:
    with _lock:
        return _speak_started_at is not None


def _cancel_watchdog_timer() -> None:
    global _watchdog_timer
    timer = _watchdog_timer
    _watchdog_timer = None
    if timer is not None:
        try:
            timer.cancel()
        except Exception:
            pass


def register_subprocess(proc: Any) -> None:
    global _active_proc, _active_pid
    with _lock:
        _active_proc = proc
        _active_pid = int(getattr(proc, "pid", 0) or 0) or None


def clear_subprocess() -> None:
    global _active_proc, _active_pid
    with _lock:
        _active_proc = None
        _active_pid = None


def begin_speak_session() -> int:
    global _speak_session_id, _speak_started_at, _speak_started_wall, _pending_speak_timeout
    with _lock:
        _cancel_watchdog_timer()
        _speak_session_id += 1
        session = _speak_session_id
        _speak_started_at = time.monotonic()
        _speak_started_wall = time.time()
        max_seconds = _resolve_watchdog_seconds()
        _pending_speak_timeout = None
        _schedule_watchdog_locked(session, max_seconds)
    return session


def end_speak_session() -> None:
    global _speak_started_at, _speak_started_wall, _speak_session_id
    with _lock:
        _cancel_watchdog_timer()
        _speak_started_at = None
        _speak_started_wall = None
        _speak_session_id += 1
        clear_subprocess()


def _schedule_watchdog_locked(session_id: int, max_seconds: float) -> None:
    global _watchdog_timer

    def _fire() -> None:
        with _lock:
            if session_id != _speak_session_id:
                return
            if _speak_started_at is None:
                return
        if _should_skip_watchdog_kill():
            logger.info("[TTS_WATCHDOG] skip kill: completion hang recovery active")
            end_speak_session()
            return
        kill_stuck_speech(
            f"speak exceeded {max_seconds:.0f}s",
            from_watchdog=True,
        )

    timer = threading.Timer(max_seconds, _fire)
    timer.daemon = True
    timer.start()
    _watchdog_timer = timer


def _should_skip_watchdog_kill() -> bool:
    try:
        from voice.audio_status import (
            mark_speech_success_heuristic_active,
            playback_audible_confirmed,
            recent_completion_hang_success,
            record_completion_hang,
        )
        from voice.pyttsx3_completion import mark_completion_hang_success

        if recent_completion_hang_success(within_seconds=20.0):
            return True
        elapsed = get_speak_elapsed_ms()
        if playback_audible_confirmed() and elapsed is not None and elapsed >= 300.0:
            mark_speech_success_heuristic_active()
            record_completion_hang()
            mark_completion_hang_success()
            return True
    except Exception:
        pass
    return False


def kill_stuck_speech(reason: str, *, from_watchdog: bool = False) -> None:
    global _last_kill_reason
    label = "killed stuck speech" if from_watchdog else "speech stopped"
    _last_kill_reason = (reason or label)[:300]
    print(f"[TTS_WATCHDOG] {label}: {_last_kill_reason}", flush=True)
    logger.warning("[TTS_WATCHDOG] %s: %s", label, _last_kill_reason)

    proc = None
    with _lock:
        proc = _active_proc
    if proc is not None:
        from voice.tts_subprocess import terminate_process_tree

        terminate_process_tree(proc)

    try:
        from voice.audio_status import record_normal_speech_failure, record_tts_timeout_kill

        record_tts_timeout_kill(_last_kill_reason)
        record_normal_speech_failure(_last_kill_reason)
    except Exception:
        pass

    try:
        from conversation.semantic_stream.engine import on_jarvis_speaking_end

        on_jarvis_speaking_end()
    except Exception:
        pass

    msg = f"TTS timeout: {_last_kill_reason}"
    try:
        from ui.overlay_app import notify_overlay_error

        notify_overlay_error(msg[:200])
    except Exception:
        pass

    end_speak_session()


def stop_speech_hard() -> str:
    """Kill active subprocess, async worker, streaming; clear SPEAK overlay."""
    kill_stuck_speech("stop speech hard", from_watchdog=False)
    try:
        from voice.tts import shutdown_tts_service

        shutdown_tts_service(join_timeout=0.5)
    except Exception:
        pass
    try:
        from voice.streaming_player import request_stop_speaking

        request_stop_speaking()
    except Exception:
        pass
    try:
        from ui.overlay_app import notify_overlay_tts_finished

        notify_overlay_tts_finished()
    except Exception:
        pass
    return _last_kill_reason or "stopped"
