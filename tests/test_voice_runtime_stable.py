"""Emergency stable voice runtime preset tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.types import CommandRequest, Intent


def _reload_config(monkeypatch, **env):
    import importlib

    import config
    import voice.runtime_mode as runtime_mode

    for key, val in env.items():
        if val is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(val))
    importlib.reload(config)
    importlib.reload(runtime_mode)
    config.apply_voice_runtime_mode()
    return config


def test_stable_mode_overrides_unsafe_keys(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    monkeypatch.setenv("STT_STREAMING_BUFFER_ENABLED", "true")
    monkeypatch.setenv("STT_MULTIPASS_ENABLED", "true")
    monkeypatch.setenv("STT_STACK_ENABLED", "true")
    monkeypatch.setenv("STT_DEVICE", "cuda")
    monkeypatch.setenv("STT_MODEL", "medium")
    monkeypatch.setenv("TTS_STREAMING_ENABLED", "true")
    cfg = _reload_config(monkeypatch)
    assert cfg.VOICE_RUNTIME_STABLE is True
    assert cfg.STT_STREAMING_BUFFER_ENABLED is False
    assert cfg.STT_MULTIPASS_ENABLED is False
    assert cfg.STT_STACK_ENABLED is False
    assert cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED is False
    assert cfg.STT_RETRY_ON_UNKNOWN is False
    assert cfg.STT_DEVICE_REQUEST == "cpu"
    assert cfg.STT_MODEL == "small"
    assert cfg.STT_BEAM_SIZE == 2
    assert cfg.STT_COMPUTE_TYPE == "int8"
    assert cfg.TTS_FORCE_ENGINE == "pyttsx3"
    assert cfg.TTS_STREAMING_ENABLED is False
    assert cfg.TTS_BARGE_IN_ENABLED is False
    assert cfg.TTS_ASYNC is False
    assert cfg.TTS_SAFE_MODE is True
    assert cfg.TTS_BACKEND == "subprocess_pyttsx3"
    assert cfg.STT_TIMEOUT_SECONDS <= 12.0
    assert cfg.TTS_TIMEOUT_SECONDS <= 8.0


def test_streaming_disabled_when_stable(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    monkeypatch.setenv("STT_STREAMING_BUFFER_ENABLED", "true")
    _reload_config(monkeypatch)
    from voice.streaming_stt import is_streaming_stt_enabled

    assert is_streaming_stt_enabled() is False


def test_multipass_disabled_when_stable(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    monkeypatch.setenv("STT_MULTIPASS_ENABLED", "true")
    _reload_config(monkeypatch)
    from voice.stt_stack.multipass import is_multipass_enabled

    assert is_multipass_enabled() is False


def test_direct_speech_uses_pyttsx3_direct():
    from actions.voice_audio_actions import TestDirectSpeechAction

    with patch("voice.tts_pyttsx3.NORMAL_DIRECT_SPEAKER") as direct:
        result = TestDirectSpeechAction().execute(
            CommandRequest(raw_text="test direct speech", intent=Intent.TEST_DIRECT_SPEECH)
        )
    direct.assert_called_once()
    assert "Jarvis direct speech test" in direct.call_args[0][0]
    assert result.status.value == "success"


def test_stable_wake_uses_fast_stt_not_multipass(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    _reload_config(monkeypatch)
    app = MagicMock()
    app.runtime = MagicMock()
    app.runtime.acquire_wake_listening_session.return_value = True
    app.runtime.overlay_enabled = False
    wav = Path("wake.wav")
    with (
        patch("voice.microphone.record_for_seconds", return_value=wav),
        patch("voice.transcriber.transcribe_wake_audio_fast") as fast,
        patch("voice.transcriber.transcribe_audio_detailed") as slow,
        patch("voice.wakeword_loop.process_voice_transcript") as route,
        patch("ui.overlay_app.notify_overlay_heard_transcript"),
        patch("ui.overlay_app.notify_overlay_transcript"),
        patch("ui.overlay_app.notify_overlay_listening"),
        patch("ui.overlay_app.notify_overlay_transcribing"),
        patch("voice.wake_greeting.play_wake_greeting_async"),
        patch("voice.latency_tracker.begin_voice_command"),
        patch("voice.latency_tracker.mark_wake_detected"),
        patch("voice.latency_tracker.finish_and_log"),
        patch("voice.latency_tracker.set_record_ms"),
        patch("voice.latency_tracker.set_transcribe_ms"),
        patch("voice.privacy.ensure_no_audio_persistence"),
        patch("voice.stt_handling.record_stt_result"),
        patch("voice.wake_greeting.strip_wake_phrase_from_transcript", side_effect=lambda t: t),
        patch("voice.normalization.normalize_wake_transcript", side_effect=lambda t: t),
        patch("voice.streaming_stt.is_streaming_stt_enabled", return_value=False),
    ):
        from voice.transcriber import TranscriptionResult

        fast.return_value = TranscriptionResult(
            text="open dashboard",
            language="en",
            model="small",
            device="cpu",
            compute_type="int8",
            low_confidence=False,
        )
        from voice.wakeword_loop import run_post_wake_listening_session

        run_post_wake_listening_session(app, session_already_acquired=True)
    slow.assert_not_called()
    fast.assert_called_once()
    route.assert_called_once()


def test_empty_transcript_guidance_visible():
    from voice.stt_diagnostics import reset_stt_diagnostics
    from voice.stt_empty_guidance import (
        EMPTY_WAKE_HINT,
        PRIMARY_EMPTY_WAKE_MSG,
        notify_empty_wake_transcript,
    )

    reset_stt_diagnostics()
    msg1 = notify_empty_wake_transcript()
    assert PRIMARY_EMPTY_WAKE_MSG in msg1
    msg2 = notify_empty_wake_transcript()
    assert EMPTY_WAKE_HINT in msg2 or "open dashboard" in msg2


def test_tts_failure_surfaces_on_overlay():
    from voice.tts_playback_trace import record_playback_failure

    with patch("ui.overlay_app.notify_overlay_error") as err:
        record_playback_failure(RuntimeError("speaker offline"), engine="pyttsx3")
    err.assert_called()


def test_voice_smoke_test_registered():
    from brain.intent_classifier import classify_rules

    assert classify_rules("voice smoke test").intent == Intent.VOICE_SMOKE_TEST


def test_stable_mode_forces_sync_tts(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    cfg = _reload_config(monkeypatch)
    assert cfg.TTS_ASYNC is False
    from voice.audio_status import set_selected_verified_audio_backend
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND

    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    svc = __import__("voice.tts", fromlist=["TTSService"]).TTSService(enabled=True)
    with patch.object(svc, "_speak_with_timeout", return_value=True) as sync:
        with patch.object(svc, "speak_async") as async_speak:
            assert svc.speak("hello") is True
    sync.assert_called_once()
    async_speak.assert_not_called()


def test_verified_backend_overrides_edge_tts_config(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "")
    cfg = _reload_config(monkeypatch)
    assert cfg.TTS_SAFE_MODE is not True or not cfg.VOICE_RUNTIME_STABLE
    from voice.audio_status import set_selected_verified_audio_backend
    from voice.tts_backend import get_active_tts_backend, prefer_subprocess_pyttsx3
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND

    monkeypatch.setattr(cfg, "TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr(cfg, "TTS_FORCE_ENGINE", "edge_tts", raising=False)
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    assert get_active_tts_backend() == SHELL_SUBPROCESS_BACKEND
    assert prefer_subprocess_pyttsx3() is True


def test_stable_speak_uses_subprocess_pyttsx3(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    _reload_config(monkeypatch)
    from voice.audio_status import set_selected_verified_audio_backend
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND
    from voice.tts import TTSService

    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    svc = TTSService(enabled=True)
    with patch("voice.tts_subprocess.speak_subprocess_pyttsx3") as sub:
        from voice.tts_subprocess import SubprocessTtsResult

        sub.return_value = SubprocessTtsResult(exit_code=0, stdout="", stderr="")
        with patch.object(svc, "_notify_tts_started", lambda: None):
            with patch.object(svc, "_notify_tts_finished", lambda: None):
                svc._speak_blocking("stable hello")
    sub.assert_called_once()
    assert sub.call_args[0][0] == "stable hello"


def test_stable_speak_subprocess_failure_no_fallback(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    _reload_config(monkeypatch)
    from voice.audio_status import set_selected_verified_audio_backend
    from voice.tts import TTSError, TTSService
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND

    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    svc = TTSService(enabled=True)
    with patch("voice.tts_subprocess.speak_subprocess_pyttsx3") as sub:
        from voice.tts_subprocess import SubprocessTtsResult

        sub.return_value = SubprocessTtsResult(
            exit_code=1, stdout="", stderr="fail", timed_out=False
        )
        with patch.object(svc, "_notify_tts_started", lambda: None):
            with patch.object(svc, "_notify_tts_finished", lambda: None):
                with pytest.raises(TTSError):
                    svc._speak_blocking("fail")


def test_stable_speak_uses_direct_pyttsx3_when_forced(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    _reload_config(monkeypatch)
    from voice.audio_status import set_force_direct_normal_mode
    from voice.audio_status import set_selected_verified_audio_backend
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND
    from voice.tts import TTSService

    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    set_force_direct_normal_mode(True)
    svc = TTSService(enabled=True)
    with patch("voice.tts_pyttsx3.NORMAL_DIRECT_SPEAKER") as direct:
        with patch.object(svc, "_notify_tts_started", lambda: None):
            with patch.object(svc, "_notify_tts_finished", lambda: None):
                svc._speak_blocking("stable hello")
    direct.assert_called_once()
    assert direct.call_args[0][0] == "stable hello"


def test_unverified_stable_speak_returns_false(monkeypatch):
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "stable")
    _reload_config(monkeypatch)
    from voice.tts import TTSService

    svc = TTSService(enabled=True)
    with patch("ui.overlay_app.notify_overlay_error") as err:
        assert svc.speak("hello") is False
    err.assert_called()


def test_router_registry_unchanged():
    from actions.registry import ActionRegistry
    from brain.router import CommandRouter

    reg = ActionRegistry()
    router = CommandRouter(registry=reg)
    assert router.registry is reg
    assert "open_trading_dashboard" in reg._actions
