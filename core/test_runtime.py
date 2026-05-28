"""Pytest / CI runtime shutdown helpers (Phase 41.5)."""

from __future__ import annotations

import os
import threading
import time
from typing import Iterable

from core.logger import setup_logger

logger = setup_logger("jarvis.core.test_runtime")

_JARVIS_THREAD_PREFIXES = (
    "jarvis-",
    "Jarvis",
)


def is_test_mode() -> bool:
    """True during pytest or when JARVIS_TEST_MODE is set."""
    if os.getenv("JARVIS_TEST_MODE", "").lower() in {"1", "true", "yes"}:
        return True
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def allow_audio_playback() -> bool:
    """Opt-in real speakers for tests that explicitly need playback."""
    if not is_test_mode():
        return True
    return os.getenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "").lower() in {"1", "true", "yes"}


def list_jarvis_threads() -> list[threading.Thread]:
    out: list[threading.Thread] = []
    for thread in threading.enumerate():
        name = thread.name or ""
        if any(name.startswith(p) for p in _JARVIS_THREAD_PREFIXES):
            out.append(thread)
    return out


def list_lingering_jarvis_threads(*, include_daemon: bool = False) -> list[threading.Thread]:
    """Non-daemon JARVIS threads, or all alive JARVIS threads when include_daemon."""
    threads = list_jarvis_threads()
    if include_daemon:
        return [t for t in threads if t.is_alive()]
    return [t for t in threads if t.is_alive() and not t.daemon]


def _join_threads(threads: Iterable[threading.Thread], *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    for thread in threads:
        remaining = max(0.05, deadline - time.monotonic())
        if thread is threading.current_thread():
            continue
        if thread.is_alive():
            thread.join(timeout=remaining)


def shutdown_jarvis_test_runtime(*, join_timeout: float = 1.5) -> None:
    """
    Best-effort teardown between pytest cases.
    Does not skip tests or hide failures — only stops background workers.
    """
    try:
        from voice.streaming_player import reset_streaming_player

        reset_streaming_player()
    except Exception as exc:
        logger.debug("streaming reset: %s", exc)

    try:
        from voice.tts_watchdog import end_speak_session

        end_speak_session()
    except Exception as exc:
        logger.debug("tts watchdog reset: %s", exc)

    try:
        from voice.tts import shutdown_tts_service

        shutdown_tts_service(join_timeout=join_timeout)
    except Exception as exc:
        logger.debug("tts shutdown: %s", exc)

    try:
        from voice.latency_tracker import reset_latency_tracker

        reset_latency_tracker()
    except Exception as exc:
        logger.debug("latency reset: %s", exc)

    try:
        from voice.transcriber import reset_model_cache

        reset_model_cache()
    except Exception as exc:
        logger.debug("stt cache reset: %s", exc)

    try:
        from voice import audio_devices

        audio_devices.set_session_output_device(None)
    except Exception as exc:
        logger.debug("audio device reset: %s", exc)

    try:
        import sounddevice as sd

        sd.stop()
    except Exception as exc:
        logger.debug("sounddevice stop: %s", exc)

    try:
        from ui.overlay_app import reset_overlay_controller, stop_all_overlay_controllers

        stop_all_overlay_controllers()
        reset_overlay_controller()
    except Exception as exc:
        logger.debug("overlay reset: %s", exc)

    try:
        from voice.wake_diagnostics import reset_wake_diagnostics
        from voice.stt_diagnostics import reset_stt_diagnostics
        from voice.voice_debug_store import reset_voice_debug_store
        from voice.audio_status import reset_audio_status
        from voice.tts_status import reset_tts_status_cache

        reset_wake_diagnostics()
        reset_stt_diagnostics()
        reset_voice_debug_store()
        reset_audio_status()
        reset_tts_status_cache()
    except Exception as exc:
        logger.debug("diagnostics reset: %s", exc)

    try:
        from services.runtime_monitor import get_runtime_monitor

        get_runtime_monitor().stop()
    except Exception as exc:
        logger.debug("runtime monitor stop: %s", exc)

    _join_threads(list_jarvis_threads(), timeout=join_timeout)
