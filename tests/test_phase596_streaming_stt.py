"""Phase 59.6 — streaming STT resilience and diagnostics."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from services.runtime_monitor import OperationTimeoutError
from voice.streaming_stt.session_policy import (
    is_streaming_stt_enabled_for_session,
    partial_timeout_count,
    record_partial_stt_timeout,
    reset_streaming_session,
)
from voice.streaming_stt.stream_session import StreamingSttSession


def _tone(seconds: float = 0.1, sr: int = 16000) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture(autouse=True)
def _reset_policy():
    reset_streaming_session()
    yield
    reset_streaming_session()


def test_record_partial_timeout_requires_three_failures(monkeypatch) -> None:
    monkeypatch.setattr("config.STT_STREAM_PARTIAL_MAX_FAILURES", 3, raising=False)
    monkeypatch.setattr("config.STT_STREAM_STARTUP_GRACE_SECONDS", 0.0, raising=False)
    reset_streaming_session()
    assert record_partial_stt_timeout() is False
    assert record_partial_stt_timeout() is False
    assert record_partial_stt_timeout() is True
    assert not is_streaming_stt_enabled_for_session()
    assert partial_timeout_count() == 3


def test_stream_session_keeps_alive_on_timeout_with_audio(monkeypatch) -> None:
    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_STREAM_STARTUP_GRACE_SECONDS", 0.0, raising=False)
    monkeypatch.setattr("config.STT_STREAM_PARTIAL_MAX_FAILURES", 5, raising=False)
    monkeypatch.setattr("config.STT_STREAM_PARTIAL_RETRY_COUNT", 0, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.STT_PARTIAL_INTERVAL_MS", 10, raising=False)
    monkeypatch.setattr("config.STT_STREAM_ENDPOINT_SILENCE_MS", 5000, raising=False)
    monkeypatch.setattr("config.STT_STREAM_MIN_PARTIAL_CONTEXT_MS", 50, raising=False)

    calls = {"n": 0}

    def _partial(_audio, _sr):
        calls["n"] += 1
        raise OperationTimeoutError("stt.stream.partial timed out after 2.5s")

    monkeypatch.setattr("voice.streaming_stt.transcribe.transcribe_stream_partial", _partial)

    session = StreamingSttSession(audio_feed=lambda: _tone(0.1), partial_interval_ms=10)
    loud = (_tone(0.15) * 3.0).astype(np.float32)
    for _ in range(8):
        session.feed_audio(loud)

    result = session.run_until_endpoint(max_seconds=0.35)
    assert is_streaming_stt_enabled_for_session()
    assert calls["n"] >= 1
    assert result.partial_updates == 0


def test_streaming_stt_test_command_synthetic(monkeypatch) -> None:
    from voice.streaming_stt.test_harness import run_streaming_stt_test

    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)

    def _fast(_audio, _sr):
        return "hello"

    with patch("voice.streaming_stt.transcribe.transcribe_stream_partial", side_effect=_fast), patch(
        "voice.streaming_stt.stream_session.is_streaming_stt_enabled",
        return_value=True,
    ):
        result = run_streaming_stt_test(listen_seconds=0.4, use_live_mic=False)
    assert "Streaming STT diagnostics" in result.report
    assert is_streaming_stt_enabled_for_session()
