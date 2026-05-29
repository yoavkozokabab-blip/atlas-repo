"""Phase 41.5 — test suite reliability and runtime resource stabilization."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from core.test_runtime import (
    list_jarvis_threads,
    list_lingering_jarvis_threads,
    shutdown_jarvis_test_runtime,
)
from ui.overlay_app import OverlayController, reset_overlay_controller, stop_all_overlay_controllers
from voice.tts import TTSService, shutdown_tts_service


def _fresh_thread_registry(monkeypatch):
    import core.thread_registry as thread_registry

    reg = thread_registry.ThreadRegistry()
    monkeypatch.setattr(thread_registry, "_registry", reg)
    return reg


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

    with (
        patch("voice.tts_playback_trace.is_tts_safe_mode", return_value=False),
        patch.object(svc, "_speak_with_timeout", side_effect=slow_speak),
    ):
        svc.speak_async("hello")
    assert svc._worker is not None
    done.set()
    svc.shutdown_worker(join_timeout=2.0)
    shutdown_tts_service(join_timeout=2.0)
    assert svc._worker is None or not svc._worker.is_alive()


def test_thread_registry_detects_dead_critical_voice_and_tts_threads(monkeypatch):
    reg = _fresh_thread_registry(monkeypatch)
    threads = [
        threading.Thread(target=lambda: None, name="jarvis-voice", daemon=True),
        threading.Thread(target=lambda: None, name="jarvis-tts", daemon=True),
    ]
    for thread in threads:
        thread.start()
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        reg.register(thread.name, thread)

    dead = set(reg.heartbeat_check())
    assert {"jarvis-voice", "jarvis-tts"}.issubset(dead)


def test_tray_voice_thread_registers_actual_thread_for_dead_detection(monkeypatch):
    from core.runtime_state import RuntimeState
    from ui.tray_app import JarvisTrayApp

    reg = _fresh_thread_registry(monkeypatch)
    runtime = RuntimeState()
    runtime.set_voice(True)
    started = threading.Event()

    def _voice_loop(_app, *, hotkey=False, runtime=None):
        started.set()

    app = MagicMock()
    app.runtime = runtime
    app._running = True
    tray = JarvisTrayApp(app, runtime=runtime)
    monkeypatch.setattr("voice.voice_loop.run_voice_loop", _voice_loop)

    tray._start_voice_background()
    assert started.wait(timeout=1.0)
    assert tray._voice_thread is not None
    tray._voice_thread.join(timeout=1.0)
    assert not tray._voice_thread.is_alive()
    assert reg.snapshot()["jarvis-voice-loop"] is False
    assert "jarvis-voice-loop" in reg.heartbeat_check()


def test_tts_async_worker_registers_actual_thread_and_deregisters(monkeypatch):
    reg = _fresh_thread_registry(monkeypatch)
    svc = TTSService(enabled=True)
    started = threading.Event()
    release = threading.Event()

    def _slow_speak(_safe: str) -> bool:
        started.set()
        release.wait(timeout=5.0)
        return True

    with (
        patch("voice.tts_playback_trace.is_tts_safe_mode", return_value=False),
        patch.object(svc, "_speak_with_timeout", side_effect=_slow_speak),
    ):
        svc.speak_async("hello")

    assert started.wait(timeout=1.0)
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if reg.snapshot().get("jarvis-tts") is True:
            break
        time.sleep(0.01)
    assert reg.snapshot()["jarvis-tts"] is True

    release.set()
    svc.shutdown_worker(join_timeout=2.0)
    assert "jarvis-tts" not in reg.registered_names()


def test_playback_guard_skips_mp3_in_test_mode(monkeypatch):
    from pathlib import Path

    from voice.playback_guard import should_play_audio
    from voice.tts_edge import _play_mp3

    monkeypatch.delenv("JARVIS_ALLOW_AUDIO_PLAYBACK", raising=False)
    with patch("voice.tts_playback_trace.is_tts_safe_mode", return_value=False):
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
