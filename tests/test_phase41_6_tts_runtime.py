"""Phase 41.6 — TTS runtime fix: safe mode, failures, fallbacks, direct speech."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from actions.voice_audio_actions import (
    ShowTtsThreadsAction,
    TestDirectSpeechAction,
    TestNormalSpeechPathAction,
)
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from voice.audio_status import (
    format_audio_status,
    get_audio_status,
    reset_audio_status,
    set_selected_verified_audio_backend,
)
from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND, SHELL_EXACT_CODE
from voice.playback_guard import should_play_audio
from voice.speech_controller import speak_text, stop_speaking
from voice.tts import TTSService
from voice.tts_playback_trace import (
    get_playback_snapshot,
    is_tts_safe_mode,
    record_playback_failure,
    reset_playback_trace,
)
from voice.tts_thread_status import format_tts_threads


@pytest.fixture(autouse=True)
def _reset_trace():
    reset_playback_trace()
    reset_audio_status()
    yield
    reset_playback_trace()
    reset_audio_status()


@pytest.fixture
def verified_shell_backend():
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    yield
    reset_audio_status()


def test_tts_safe_mode_config(monkeypatch):
    monkeypatch.setattr("config.VOICE_RUNTIME_STABLE", False, raising=False)
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    assert is_tts_safe_mode() is True
    monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
    assert is_tts_safe_mode() is False


def test_safe_mode_allows_playback_in_test_mode(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    monkeypatch.delenv("JARVIS_ALLOW_AUDIO_PLAYBACK", raising=False)
    assert should_play_audio() is True


def test_playback_failure_not_swallowed(capsys):
    record_playback_failure(
        RuntimeError("speaker offline"),
        engine="pyttsx3",
        path="test",
        context="unit",
    )
    snap = get_playback_snapshot()
    assert snap.failure_count == 1
    assert "speaker offline" in snap.last_exception
    out = capsys.readouterr().out
    assert "[TTS ERROR]" in out


def test_audio_status_includes_failure_fields():
    record_playback_failure(ValueError("bad wav"), engine="edge_mp3", path="mp3")
    text = format_audio_status()
    status = get_audio_status()
    assert status.playback_failure_count == 1
    assert "bad wav" in status.last_exception
    assert "Playback failure count: 1" in text
    assert "Last exception:" in text


def test_speak_text_safe_mode_uses_subprocess(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    called: list[str] = []

    def _sub(text: str, **kwargs):
        from voice.tts_subprocess import SubprocessTtsResult

        called.append(text)
        return SubprocessTtsResult(exit_code=0, stdout="", stderr="")

    monkeypatch.setattr("voice.tts_subprocess.speak_subprocess_pyttsx3", _sub)
    provider = speak_text("Hello safe mode")
    assert provider == SHELL_SUBPROCESS_BACKEND
    assert called == ["Hello safe mode"]


def test_safe_mode_ignores_stop_speaking(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    from voice.streaming_player import request_stop_speaking

    request_stop_speaking()
    stop_speaking()
    from voice.streaming_player import is_stop_requested

    assert is_stop_requested() is True


def test_unverified_stable_blocks_speech(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    svc = TTSService(enabled=True)
    with patch("ui.overlay_app.notify_overlay_error") as err:
        assert svc.speak("blocked") is False
    err.assert_called()


def test_shell_exact_argv_matches_user_command():
    from voice.tts_subprocess import build_shell_exact_argv

    argv = build_shell_exact_argv()
    assert argv == ["py", "-3", "-c", SHELL_EXACT_CODE]
    assert "Jarvis shell audio test from local jarvis" in SHELL_EXACT_CODE


def test_tts_service_safe_mode_bypasses_stack(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    svc = TTSService(enabled=True)
    stack_called = False
    sub_called: list[str] = []

    def _stack(_safe: str) -> str:
        nonlocal stack_called
        stack_called = True
        return "edge_tts"

    def _sub(text: str, **kwargs):
        from voice.tts_subprocess import SubprocessTtsResult

        sub_called.append(text)
        return SubprocessTtsResult(exit_code=0, stdout="", stderr="")

    monkeypatch.setattr("voice.speech_controller.speak_text", _stack)
    monkeypatch.setattr("voice.tts_subprocess.speak_subprocess_pyttsx3", _sub)
    assert svc._speak_blocking("hi") is True
    assert stack_called is False
    assert sub_called == ["hi"]


def test_streaming_retry_blocking_on_failure(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
    monkeypatch.setattr("config.TTS_STREAMING_ENABLED", True, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    retries: list[str] = []

    def _stream_fail(*_a, **_k):
        return False

    def _pyttsx3(_safe: str) -> None:
        retries.append("blocking")

    monkeypatch.setattr("config.VOICE_RUNTIME_STABLE", False, raising=False)
    monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
    monkeypatch.setattr(
        "voice.speech_controller.stream_mp3_chunks_incremental",
        _stream_fail,
    )
    monkeypatch.setattr(
        "voice.engines.registry.synthesize_with_fallback",
        lambda *a, **k: ("edge_tts", iter([b"x"])),
    )
    monkeypatch.setattr("voice.viseme_timeline.build_viseme_frames", lambda *a, **k: [])
    monkeypatch.setattr(
        "voice.tts.TTSService._speak_pyttsx3",
        lambda self, safe: retries.append(safe),
    )
    provider = speak_text("retry me")
    assert provider == "pyttsx3_blocking_retry"
    assert retries == ["retry me"]


def test_async_failure_retries_sync_then_records(monkeypatch, capsys):
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("voice.tts_playback_trace.is_tts_safe_mode", lambda: False)
    svc = TTSService(enabled=True)
    attempts = {"n": 0}

    def _blocking(_safe: str) -> bool:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise Exception("async path fail")
        return True

    workers: list[threading.Thread] = []
    real_start = threading.Thread.start

    def _track(self, *args, **kwargs):
        workers.append(self)
        return real_start(self, *args, **kwargs)

    with (
        patch.object(threading.Thread, "start", _track),
        patch.object(svc, "_speak_blocking", side_effect=_blocking),
    ):
        assert svc.speak("hello") is True
        for w in workers:
            w.join(timeout=5.0)


def test_direct_speech_action(monkeypatch):
    monkeypatch.setattr(
        "voice.tts_pyttsx3.speak_pyttsx3_direct",
        lambda text, *, rate_raw: None,
    )
    action = TestDirectSpeechAction()
    result = action.execute(CommandRequest(raw_text="test direct speech", intent=Intent.TEST_DIRECT_SPEECH))
    assert result.status == ActionStatus.SUCCESS
    assert "Direct pyttsx3 speech OK" in result.summary


def test_show_tts_threads_action():
    action = ShowTtsThreadsAction()
    result = action.execute(CommandRequest(raw_text="show tts threads", intent=Intent.SHOW_TTS_THREADS))
    assert result.status == ActionStatus.SUCCESS
    assert "TTS threads" in result.summary


def test_classify_direct_speech_and_threads():
    assert classify_rules("test direct speech").intent == Intent.TEST_DIRECT_SPEECH
    assert classify_rules("show tts threads").intent == Intent.SHOW_TTS_THREADS


def test_format_tts_threads():
    text = format_tts_threads()
    assert "TTS threads" in text
    assert "count:" in text


def test_pyttsx3_direct_records_finish(monkeypatch, capsys):
    engine = MagicMock()
    order: list[str] = []

    def _init():
        order.append("init")
        return engine

    def _say(_text: str) -> None:
        order.append("say")

    def _wait() -> None:
        order.append("runAndWait")

    engine.say.side_effect = _say
    engine.runAndWait.side_effect = _wait

    monkeypatch.setattr("pyttsx3.init", _init)
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    from voice.tts_pyttsx3 import reset_pyttsx3_engine, speak_pyttsx3_direct

    reset_pyttsx3_engine()
    speak_pyttsx3_direct("block test", rate_raw="")
    assert order == ["init", "say", "runAndWait"]
    out = capsys.readouterr().out
    assert "[TTS_DIRECT] init" in out
    assert "[TTS_DIRECT] runAndWait end" in out
    assert "[TTS_DIRECT] success" in out
    snap = get_playback_snapshot()
    assert snap.last_engine == "pyttsx3_direct"
    assert snap.failure_count == 0


def test_speak_overlay_only_while_subprocess_running(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    svc = TTSService(enabled=True)
    events: list[str] = []

    def _sub(text: str, **kwargs):
        events.append("subprocess_start")
        cb = kwargs.get("on_playback_start")
        if cb:
            cb()
            events.append("overlay_speak")
        events.append("subprocess_end")
        from voice.tts_subprocess import SubprocessTtsResult

        return SubprocessTtsResult(exit_code=0, stdout="", stderr="")

    monkeypatch.setattr("voice.tts_subprocess.speak_subprocess_pyttsx3", _sub)
    monkeypatch.setattr(svc, "_notify_tts_started", lambda: events.append("notify_started"))
    monkeypatch.setattr(svc, "_notify_tts_finished", lambda: events.append("notify_finished"))
    svc._speak_blocking("hello")
    assert "overlay_speak" in events
    assert events.index("notify_finished") > events.index("overlay_speak")


def test_tts_success_on_subprocess_exit_zero(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    svc = TTSService(enabled=True)
    recorded: list[str] = []

    def _sub(text: str, **kwargs):
        from voice.tts_subprocess import SubprocessTtsResult

        return SubprocessTtsResult(exit_code=0, stdout="", stderr="")

    def _record(provider: str, text: str) -> None:
        recorded.append(f"success:{provider}")

    monkeypatch.setattr("voice.tts_subprocess.speak_subprocess_pyttsx3", _sub)
    monkeypatch.setattr(svc, "_record_success", _record)
    monkeypatch.setattr(svc, "_notify_tts_started", lambda: None)
    monkeypatch.setattr(svc, "_notify_tts_finished", lambda: None)
    assert svc._speak_blocking("ok") is True
    assert recorded == [f"success:{SHELL_SUBPROCESS_BACKEND}"]


def test_subprocess_command_escapes_text():
    from voice.tts_subprocess import build_pyttsx3_subprocess_argv, build_pyttsx3_subprocess_code

    text = 'He said "hello" and \\bye'
    code = build_pyttsx3_subprocess_code(text)
    assert repr(text) in code
    argv = build_pyttsx3_subprocess_argv(text)
    assert argv[:3] == ["py", "-3", "-c"]


def test_subprocess_timeout_recorded(monkeypatch):
    import subprocess

    class _Proc:
        returncode = None

        def communicate(self, timeout=None):
            if self.returncode is not None:
                return ("", "")
            raise subprocess.TimeoutExpired(cmd="py", timeout=timeout)

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr("voice.tts_subprocess.subprocess.Popen", lambda *a, **k: _Proc())
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    from voice.tts_subprocess import speak_subprocess_pyttsx3

    result = speak_subprocess_pyttsx3("timeout test", timeout_seconds=0.01)
    assert result.timed_out is True
    assert result.exit_code != 0
    from voice.audio_status import get_audio_status

    assert get_audio_status().last_subprocess_error is not None


def test_subprocess_success_exit_zero(monkeypatch):
    class _Proc:
        returncode = 0

        def communicate(self, timeout=None):
            return ("", "")

    monkeypatch.setattr("voice.tts_subprocess.subprocess.Popen", lambda *a, **k: _Proc())
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    from voice.tts_subprocess import speak_subprocess_pyttsx3

    result = speak_subprocess_pyttsx3("ok")
    assert result.ok is True
    from voice.audio_status import get_audio_status

    assert get_audio_status().last_subprocess_exit_code == 0


def test_audio_status_shows_subprocess_backend(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    text = format_audio_status()
    assert f"Verified backend: {SHELL_SUBPROCESS_BACKEND}" in text
    assert f"Active backend (routing): {SHELL_SUBPROCESS_BACKEND}" in text


def test_verified_backend_overrides_edge_when_not_safe_mode(
    monkeypatch, verified_shell_backend
):
    monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_FORCE_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_STREAMING_ENABLED", True, raising=False)
    from voice.tts_backend import get_active_tts_backend, prefer_subprocess_pyttsx3

    assert get_active_tts_backend() == SHELL_SUBPROCESS_BACKEND
    assert prefer_subprocess_pyttsx3() is True


def test_normal_speech_uses_subprocess_with_verified_not_safe(
    monkeypatch, verified_shell_backend
):
    monkeypatch.setattr("config.TTS_SAFE_MODE", False, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    svc = TTSService(enabled=True)
    stack_called = False

    def _stack(_safe: str) -> str:
        nonlocal stack_called
        stack_called = True
        return "edge_tts"

    def _sub(text: str, **kwargs):
        from voice.tts_subprocess import SubprocessTtsResult

        return SubprocessTtsResult(exit_code=0, stdout="", stderr="")

    monkeypatch.setattr("voice.speech_controller.speak_text", _stack)
    monkeypatch.setattr("voice.tts_subprocess.speak_subprocess_pyttsx3", _sub)
    with patch.object(svc, "_notify_tts_started", lambda: None):
        with patch.object(svc, "_notify_tts_finished", lambda: None):
            assert svc._speak_blocking("hi") is True
    assert stack_called is False


def test_voice_stack_profile_cannot_override_verified_stable(
    monkeypatch, verified_shell_backend, tmp_path
):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.VOICE_RUNTIME_STABLE", True, raising=False)
    monkeypatch.setattr("config.VOICE_STACK_PATH", tmp_path / "voice_stack.json", raising=False)
    from voice.voice_stack_store import VoiceStackProfile, apply_voice_profile_to_runtime, save_voice_profile

    prof = VoiceStackProfile(engine="edge_tts", voice="en-US-JennyNeural")
    save_voice_profile(prof)
    apply_voice_profile_to_runtime(prof)
    import config as cfg

    assert cfg.TTS_ENGINE == "pyttsx3"
    assert cfg.TTS_STREAMING_ENABLED is False
    assert cfg.TTS_BACKEND == SHELL_SUBPROCESS_BACKEND


def test_normal_speech_path_fails_if_edge_used_with_verified(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)

    def _factory(*_a, **_k):
        svc = MagicMock()
        svc.enabled = True
        svc.speak.return_value = True
        return svc

    monkeypatch.setattr("actions.voice_audio_actions.TTSService", _factory)
    from voice.audio_status import record_normal_speech_path

    record_normal_speech_path("edge_tts")
    result = TestNormalSpeechPathAction().execute(
        CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
    )
    assert result.status == ActionStatus.FAILED
    assert "edge_tts" in result.message.lower()


def test_stable_normal_uses_subprocess_backend(monkeypatch, verified_shell_backend):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    monkeypatch.setattr("config.VOICE_RUNTIME_STABLE", True, raising=False)
    monkeypatch.setattr("config.TTS_BACKEND", "subprocess_pyttsx3", raising=False)
    from voice.tts_backend import get_active_tts_backend, prefer_subprocess_pyttsx3
    from voice.tts_playback_trace import must_use_direct_pyttsx3

    assert prefer_subprocess_pyttsx3() is True
    assert must_use_direct_pyttsx3() is False
    assert get_active_tts_backend() == SHELL_SUBPROCESS_BACKEND
    from voice.audio_status import (
        get_audio_status,
        record_normal_speech_success,
        stable_normal_equals_direct,
    )

    record_normal_speech_success(text_preview="normal", path=SHELL_SUBPROCESS_BACKEND)
    assert stable_normal_equals_direct() is True
    status = get_audio_status()
    assert status.active_backend == SHELL_SUBPROCESS_BACKEND
    assert status.normal_speech_last_success_at is not None


def test_normal_speech_path_action_uses_tts_service(monkeypatch):
    monkeypatch.setattr("config.TTS_SAFE_MODE", True, raising=False)
    called: list[str] = []

    def _factory(*_a, **_k):
        svc = MagicMock()
        svc.enabled = True
        svc.speak.side_effect = lambda text: called.append(text) or True
        return svc

    monkeypatch.setattr("actions.voice_audio_actions.TTSService", _factory)
    result = TestNormalSpeechPathAction().execute(
        CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
    )
    assert result.status == ActionStatus.SUCCESS
    assert called == ["Jarvis normal speech path test"]


def test_classify_normal_speech_path():
    assert classify_rules("test normal speech path").intent == Intent.TEST_NORMAL_SPEECH


def test_audio_status_shows_path_comparison():
    from voice.audio_status import record_normal_speech_failure

    record_normal_speech_failure("speaker offline")
    text = format_audio_status()
    assert "Direct pyttsx3 user heard:" in text
    assert "Normal speech path last success:" in text
    assert "Last normal speech error: speaker offline" in text
