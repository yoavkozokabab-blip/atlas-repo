"""Hotfix: streaming STT must not block wake on accurate_retry / multipass."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from services.runtime_monitor import OperationTimeoutError
from voice.streaming_stt.session_policy import (
    StreamingSttFallbackError,
    disable_streaming_for_session,
    is_streaming_stt_enabled_for_session,
    record_partial_stt_timeout,
    reset_streaming_session,
)
from voice.streaming_stt.stream_session import StreamingSttSession
from voice.stt_engines.base import SttHypothesis


def _tone(seconds: float = 0.2, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture(autouse=True)
def _reset_policy():
    reset_streaming_session()
    yield
    reset_streaming_session()


def test_partial_transcribe_uses_fast_pass_only(monkeypatch):
    calls: list[str] = []

    def _hyp(_path, **kwargs):
        calls.append(str(kwargs.get("stt_pass", "full")))
        return SttHypothesis(text="open dash", engine="faster_whisper", confidence=0.8)

    monkeypatch.setattr(
        "voice.transcriber.transcribe_faster_whisper_hypothesis",
        _hyp,
    )
    from voice.streaming_stt.transcribe import transcribe_stream_partial

    text = transcribe_stream_partial(_tone(), 16000)
    assert text == "open dash"
    assert calls == ["partial"]
    assert "accurate" not in calls


def test_final_endpoint_may_accurate_retry_once(monkeypatch):
    calls: list[str] = []

    def _hyp(_path, **kwargs):
        calls.append(str(kwargs.get("stt_pass", "full")))
        if kwargs.get("stt_pass") == "accurate":
            return SttHypothesis(text="open dashboard", engine="faster_whisper", confidence=0.9)
        return SttHypothesis(text="", engine="faster_whisper", confidence=0.2)

    monkeypatch.setattr("voice.transcriber.transcribe_faster_whisper_hypothesis", _hyp)
    monkeypatch.setattr("config.STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_RETRY_ON_UNKNOWN", True, raising=False)
    monkeypatch.setattr(
        "voice.stt_stack.multipass._preview_intent_unknown",
        lambda _t: True,
    )
    monkeypatch.setattr(
        "voice.stt_stack.multipass._close_match_detected",
        lambda *_a, **_k: False,
    )

    from voice.streaming_stt.transcribe import transcribe_stream_final

    out = transcribe_stream_final(_tone(0.5), 16000, partial_text="")
    assert "dashboard" in out
    assert calls.count("partial") >= 1
    assert calls.count("accurate") == 1


def test_partial_timeout_disables_streaming_session(monkeypatch):
    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_STREAM_PARTIAL_MAX_FAILURES", 3, raising=False)
    monkeypatch.setattr("config.STT_STREAM_STARTUP_GRACE_SECONDS", 0.0, raising=False)
    reset_streaming_session()
    for _ in range(3):
        assert record_partial_stt_timeout() is (_ == 2)
    assert not is_streaming_stt_enabled_for_session()


def test_partial_timeout_grace_keeps_streaming_enabled(monkeypatch):
    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_STREAM_STARTUP_GRACE_SECONDS", 30.0, raising=False)
    from voice.streaming_stt.session_policy import record_partial_stt_timeout, reset_streaming_session

    reset_streaming_session()
    assert record_partial_stt_timeout() is False
    assert is_streaming_stt_enabled_for_session()


def test_streaming_failure_uses_fast_fallback_and_router(monkeypatch):
    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_WAKE_FALLBACK_TIMEOUT_SECONDS", 8, raising=False)

    app = MagicMock()
    app.session = MagicMock()
    app.runtime = MagicMock()
    app.runtime.acquire_wake_listening_session.return_value = True
    app.runtime.overlay_enabled = False

    wav = Path("wake.wav")

    with (
        patch("voice.microphone.record_for_seconds", return_value=wav),
        patch(
            "voice.streaming_stt.run_streaming_wake_capture",
            side_effect=StreamingSttFallbackError("partial timeout"),
        ),
        patch("voice.transcriber.transcribe_wake_audio_fast") as fast_stt,
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
        patch("voice.streaming_stt.is_streaming_stt_enabled", return_value=True),
        patch(
            "conversation.human_runtime.should_start_human_session_after_wake",
            return_value=False,
        ),
        patch("voice.wake_greeting.strip_wake_phrase_from_transcript", side_effect=lambda t: t),
        patch("voice.normalization.normalize_wake_transcript", side_effect=lambda t: t),
        patch("voice.transcriber.transcribe_audio_detailed") as slow_stt,
    ):
        from voice.transcriber import TranscriptionResult

        fast_stt.return_value = TranscriptionResult(
            text="open dashboard",
            language="en",
            model="small",
            device="cpu",
            compute_type="int8",
            low_confidence=False,
        )
        from voice.wakeword_loop import run_post_wake_listening_session

        run_post_wake_listening_session(app, session_already_acquired=True)

    slow_stt.assert_not_called()
    fast_stt.assert_called_once()
    assert fast_stt.call_args[0][0] == wav
    route.assert_called_once()
    assert route.call_args[0][1] == "open dashboard"


def test_streaming_disabled_by_default_config():
    import config as cfg

    assert cfg.STT_STREAMING_BUFFER_ENABLED is False
    assert cfg.STT_MULTIPASS_ENABLED is False
    assert cfg.STT_STACK_ENABLED is False
    assert cfg.STT_COMPUTE_TYPE == "int8"
