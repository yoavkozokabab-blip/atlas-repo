"""TTS playback tracing and failure surfacing (Phase 41.6)."""

from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts.trace")

_lock = threading.Lock()
_failure_count: int = 0
_last_exception: str = ""
_last_exception_type: str = ""
_playback_started_at: float | None = None
_last_engine: str = ""
_last_device: str = ""
_last_path: str = ""
_events: list[str] = []


@dataclass
class TtsPlaybackSnapshot:
    failure_count: int = 0
    last_exception: str = ""
    last_exception_type: str = ""
    last_engine: str = ""
    last_output_device: str = ""
    last_path: str = ""
    safe_mode: bool = False
    debug_enabled: bool = False
    recent_events: tuple[str, ...] = ()


def is_tts_safe_mode() -> bool:
    try:
        import config

        if getattr(config, "VOICE_RUNTIME_STABLE", False):
            return True
        return bool(config.TTS_SAFE_MODE)
    except Exception:
        return False


def must_use_direct_pyttsx3() -> bool:
    """In-process pyttsx3.init → say → runAndWait (fallback / forced / user-verified)."""
    try:
        from voice.audio_status import (
            get_selected_verified_audio_backend,
            is_force_direct_normal_mode,
        )
        from voice.tts_backend import prefer_subprocess_pyttsx3

        if prefer_subprocess_pyttsx3():
            return False
        if is_force_direct_normal_mode():
            return True
        if get_selected_verified_audio_backend() == "direct_pyttsx3":
            return True
    except Exception:
        pass
    return False


def is_tts_debug() -> bool:
    if is_tts_safe_mode():
        return True
    try:
        import config

        return bool(config.TTS_DEBUG_PLAYBACK)
    except Exception:
        return False


def _append_event(msg: str) -> None:
    with _lock:
        _events.append(f"{time.monotonic():.3f} {msg}")
        del _events[:-40]


def log_tts_debug(msg: str, **fields) -> None:
    if not is_tts_debug():
        return
    extra = " ".join(f"{k}={v!r}" for k, v in fields.items()) if fields else ""
    line = f"[TTS DEBUG] {msg}" + (f" {extra}" if extra else "")
    print(line, flush=True)
    logger.debug(line)
    _append_event(line)


def record_playback_start(*, engine: str, device: str, path: str) -> None:
    global _playback_started_at, _last_engine, _last_device, _last_path
    with _lock:
        _playback_started_at = time.monotonic()
        _last_engine = engine
        _last_device = device
        _last_path = path
    log_tts_debug("playback_start", engine=engine, device=device, path=path)


def record_playback_finish(*, engine: str, ok: bool, elapsed_ms: float | None = None) -> None:
    log_tts_debug(
        "playback_finish",
        engine=engine,
        ok=ok,
        elapsed_ms=round(elapsed_ms, 1) if elapsed_ms is not None else None,
    )


def record_playback_failure(
    exc: BaseException,
    *,
    engine: str = "",
    path: str = "",
    context: str = "",
) -> None:
    global _failure_count, _last_exception, _last_exception_type, _last_engine, _last_path
    tb = traceback.format_exc()
    msg = f"{type(exc).__name__}: {exc}"
    with _lock:
        _failure_count += 1
        _last_exception = msg[:500]
        _last_exception_type = type(exc).__name__
        if engine:
            _last_engine = engine
        if path:
            _last_path = path
    print(f"[TTS ERROR] {context}: {msg}" if context else f"[TTS ERROR] {msg}", flush=True)
    if is_tts_debug() and tb.strip() != "NoneType: None\n":
        print(tb[:800], flush=True)
    logger.warning("TTS playback failure (%s): %s", context or path, msg)
    _append_event(f"FAIL {context} {msg}")
    try:
        from voice.tts_status import record_tts_run

        record_tts_run(provider=engine or "unknown", error=msg)
    except Exception:
        pass
    try:
        from voice.audio_status import record_tts_failure

        record_tts_failure(error=msg, provider=engine or "unknown")
    except Exception:
        pass
    try:
        from ui.overlay_app import notify_overlay_error

        overlay_msg = f"TTS: {msg}"[:200]
        notify_overlay_error(overlay_msg)
    except Exception:
        pass


def get_playback_snapshot() -> TtsPlaybackSnapshot:
    with _lock:
        return TtsPlaybackSnapshot(
            failure_count=_failure_count,
            last_exception=_last_exception,
            last_exception_type=_last_exception_type,
            last_engine=_last_engine,
            last_output_device=_last_device,
            last_path=_last_path,
            safe_mode=is_tts_safe_mode(),
            debug_enabled=is_tts_debug(),
            recent_events=tuple(_events[-15:]),
        )


def reset_playback_trace() -> None:
    global _failure_count, _last_exception, _last_exception_type
    global _playback_started_at, _last_engine, _last_device, _last_path, _events
    with _lock:
        _failure_count = 0
        _last_exception = ""
        _last_exception_type = ""
        _playback_started_at = None
        _last_engine = ""
        _last_device = ""
        _last_path = ""
        _events.clear()
