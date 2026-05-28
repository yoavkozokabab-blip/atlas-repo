"""TTS SPEAK watchdog — hard timeout, kill subprocess, overlay recovery."""

from __future__ import annotations

import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from voice.audio_status import (
    get_audio_status,
    reset_audio_status,
    set_selected_verified_audio_backend,
)
from voice.tts import TTSService
from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND, run_subprocess_tts_argv
from voice.tts_watchdog import (
    begin_speak_session,
    end_speak_session,
    get_subprocess_timeout_seconds,
    kill_stuck_speech,
    stop_speech_hard,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_audio_status()
    end_speak_session()
    yield
    end_speak_session()
    reset_audio_status()


def test_subprocess_timeout_kills_child(monkeypatch):
    monkeypatch.setattr("voice.tts_watchdog.get_subprocess_timeout_seconds", lambda: 0.2)

    class _SlowProc:
        pid = 4242

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="py", timeout=timeout or 0.2)

        def kill(self):
            pass

    killed: list[int] = []

    def _terminate(proc):
        killed.append(getattr(proc, "pid", 0))

    monkeypatch.setattr("voice.tts_subprocess.terminate_process_tree", _terminate)
    monkeypatch.setattr(
        "voice.tts_subprocess.subprocess.Popen",
        lambda *a, **k: _SlowProc(),
    )
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")

    result = run_subprocess_tts_argv(["py", "-3", "-c", "pass"], label="TTS_TEST")
    assert result.timed_out is True
    assert killed == [4242]


def test_watchdog_kills_stuck_speech_and_sets_overlay_error():
    begin_speak_session()
    with patch("ui.overlay_app.notify_overlay_error") as err:
        kill_stuck_speech("test stuck", from_watchdog=True)
    err.assert_called_once()
    assert "test stuck" in err.call_args[0][0]
    status = get_audio_status()
    assert status.last_timeout_kill_reason is not None


def test_stop_speech_hard_clears_active_proc(monkeypatch):
    class _Proc:
        pid = 999

    monkeypatch.setattr("voice.tts_watchdog._active_proc", _Proc(), raising=False)
    monkeypatch.setattr("voice.tts_watchdog._active_pid", 999, raising=False)
    terminated: list[int] = []

    monkeypatch.setattr(
        "voice.tts_subprocess.terminate_process_tree",
        lambda p: terminated.append(p.pid),
    )
    with patch("ui.overlay_app.notify_overlay_tts_finished"):
        reason = stop_speech_hard()
    assert terminated == [999]
    assert reason


def test_no_speak_without_verified_backend(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    svc = TTSService(enabled=True)
    with patch("ui.overlay_app.notify_overlay_error") as err:
        assert svc.speak("hello") is False
    err.assert_called()


def test_speak_allowed_with_verified_backend(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    svc = TTSService(enabled=True)
    with patch.object(svc, "_speak_with_timeout", return_value=True) as sync:
        assert svc.speak("hello") is True
    sync.assert_called_once()


def test_stable_mode_speak_async_uses_sync(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    svc = TTSService(enabled=True)
    with patch.object(svc, "_speak_with_timeout", return_value=True) as sync:
        svc.speak_async("hello")
    sync.assert_called_once()


def test_stable_blocks_edge_tts_routing_flag(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    from voice.tts_backend import normal_speech_must_not_use_edge_tts

    assert normal_speech_must_not_use_edge_tts() is True


def test_startup_self_test_skipped_without_verified(monkeypatch):
    from voice.tts_startup import run_tts_startup_self_test

    monkeypatch.setattr("config.TTS_STARTUP_SELF_TEST", True, raising=False)
    with patch("voice.tts.TTSService") as svc:
        run_tts_startup_self_test(enabled=True)
    svc.assert_not_called()
    from voice.audio_status import get_audio_status

    assert "no verified" in (get_audio_status().startup_self_test or "")


def test_audio_status_shows_tts_pid_fields(monkeypatch):
    monkeypatch.setattr("voice.tts_watchdog._active_pid", 12345, raising=False)
    monkeypatch.setattr("voice.tts_watchdog._speak_started_wall", time.time(), raising=False)
    text = __import__("voice.audio_status", fromlist=["format_audio_status"]).format_audio_status()
    assert "Active TTS pid: 12345" in text
    assert "TTS elapsed ms:" in text


def test_get_subprocess_timeout_capped_at_8(monkeypatch):
    monkeypatch.setattr("config.TTS_TIMEOUT_SECONDS", 20.0, raising=False)
    monkeypatch.setattr("config.TTS_SPEAK_MAX_SECONDS", 8.0, raising=False)
    assert get_subprocess_timeout_seconds() == 8.0
