"""Phase 41.5 — test suite reliability and runtime resource stabilization."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from core.test_runtime import (
    list_jarvis_threads,
    list_lingering_jarvis_threads,
    shutdown_jarvis_test_runtime,
)
from ui.overlay_app import OverlayController, reset_overlay_controller, stop_all_overlay_controllers
from voice.tts import TTSService, shutdown_tts_service


def test_overlay_controller_stops_queue_thread():
    ctrl = OverlayController()
    thread = ctrl._queue_thread
    assert thread is not None
    ctrl.stop(join_timeout=2.0)
    assert not thread.is_alive()


def test_stop_all_overlay_controllers_cleans_orphans():
    a = OverlayController()
    b = OverlayController()
    stop_all_overlay_controllers(join_timeout=2.0)
    assert not a._queue_thread.is_alive()
    assert not b._queue_thread.is_alive()


def test_shutdown_after_overlay_tests_leaves_no_extra_queue_threads():
    before = {t.name for t in list_jarvis_threads()}
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    ctrl.on_transcribing(sub_status="partial")
    stop_all_overlay_controllers(join_timeout=2.0)
    reset_overlay_controller()
    shutdown_jarvis_test_runtime()
    after = {t.name for t in list_jarvis_threads() if t.is_alive()}
    assert "jarvis-overlay-queue" not in after or "jarvis-overlay-queue" in before


def test_tts_async_worker_joined_on_shutdown(monkeypatch):
    import config

    monkeypatch.setattr(config, "TTS_ASYNC", True, raising=False)
    svc = TTSService(enabled=True)
    done = threading.Event()

    def slow_speak(_safe: str) -> bool:
        done.wait(5)
        return True

    with patch.object(svc, "_speak_with_timeout", side_effect=slow_speak):
        svc.speak_async("hello")
    assert svc._worker is not None
    done.set()
    svc.shutdown_worker(join_timeout=2.0)
    shutdown_tts_service(join_timeout=2.0)
    assert svc._worker is None or not svc._worker.is_alive()


def test_playback_guard_skips_mp3_in_test_mode():
    from pathlib import Path

    from voice.playback_guard import should_play_audio
    from voice.tts_edge import _play_mp3

    assert not should_play_audio()
    _play_mp3(Path("nonexistent.mp3"))  # no-op, must not raise


def test_repeated_tts_shutdown_does_not_grow_workers():
    svc = TTSService(enabled=True)
    for _ in range(3):
        with patch.object(svc, "_speak_with_timeout", return_value=True):
            svc.speak_async("hi")
        svc.shutdown_worker(join_timeout=1.0)
    shutdown_tts_service(join_timeout=1.0)
    alive_tts = [t for t in list_jarvis_threads() if t.name == "jarvis-tts" and t.is_alive()]
    assert not alive_tts


def test_no_non_daemon_jarvis_threads_after_voice_cleanup():
    shutdown_jarvis_test_runtime(join_timeout=2.0)
    lingering = list_lingering_jarvis_threads(include_daemon=False)
    assert lingering == []


def test_finish_and_log_does_not_wait_long_in_test_mode():
    import time

    from voice.latency_tracker import begin_voice_command, finish_and_log

    begin_voice_command(source="test")
    t0 = time.perf_counter()
    finish_and_log(wait_for_tts=True, tts_wait_seconds=12.0)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0
