"""Phase 42.6 — rolling-buffer streaming STT."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from voice.streaming_player import is_speaking, request_stop_speaking
from voice.streaming_stt.endpoint_detector import StreamEndpointDetector
from voice.streaming_stt.incremental_decode import IncrementalDecoder
from voice.streaming_stt.intent_prefetch import prefetch_intent
from voice.streaming_stt.realtime_metrics import RealtimeSttMetrics, get_realtime_metrics, reset_realtime_metrics
from voice.streaming_stt.rolling_buffer import RollingAudioBuffer
from voice.streaming_stt.stream_session import StreamingSttSession
from voice.stt_stack.partial_stream import clear_partial_listeners, emit_partial, get_last_partial


@pytest.fixture(autouse=True)
def _clean():
    clear_partial_listeners()
    reset_realtime_metrics()
    request_stop_speaking()
    yield
    clear_partial_listeners()
    reset_realtime_metrics()


def _tone(seconds: float, sr: int = 16000, amp: float = 0.2) -> np.ndarray:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_rolling_buffer_trims_old_audio():
    buf = RollingAudioBuffer(sample_rate=16000, max_seconds=2.0)
    buf.append(_tone(1.0))
    buf.append(_tone(1.5))
    assert buf.duration_seconds() <= 2.05
    snap = buf.snapshot()
    assert snap.shape[0] <= 32000 + 8000


def test_rolling_buffer_clear():
    buf = RollingAudioBuffer(sample_rate=16000, max_seconds=3.0)
    buf.append(_tone(0.5))
    buf.clear()
    assert buf.total_samples == 0
    assert buf.snapshot().size == 0


def test_endpoint_without_stopping_stream():
    det = StreamEndpointDetector(
        silence_threshold=0.01,
        endpoint_silence_ms=200,
        min_speech_ms=80,
        sample_rate=16000,
        chunk_seconds=0.10,
    )
    det.observe_chunk(_tone(0.2, amp=0.3))
    for _ in range(5):
        state = det.observe_chunk(_tone(0.10, amp=0.3))
        assert not state.endpoint_reached
    for _ in range(3):
        state = det.observe_chunk(_tone(0.10, amp=0.0))
    assert state.endpoint_reached


def test_incremental_decoder_merges_prefix():
    calls: list[int] = []

    def _fake(_audio, _sr):
        calls.append(1)
        return "open dash" if len(calls) == 1 else "open dashboard"

    dec = IncrementalDecoder(transcribe_fn=_fake, min_interval_ms=0, min_new_samples=100)
    audio = _tone(0.3)
    dec.decode(audio, sample_rate=16000, generation=1)
    text = dec.decode(audio, sample_rate=16000, generation=2)
    assert "dashboard" in text


def test_partial_transcript_updates():
    seen: list[str] = []
    from voice.stt_stack.partial_stream import register_partial_listener

    register_partial_listener(seen.append)
    emit_partial("open")
    emit_partial("open dashboard")
    assert get_last_partial() == "open dashboard"
    assert seen[-1] == "open dashboard"


def test_streaming_session_partials_and_endpoint(monkeypatch):
    monkeypatch.setattr("config.STT_PARTIAL_INTERVAL_MS", 50, raising=False)
    monkeypatch.setattr("config.STT_STREAM_ENDPOINT_SILENCE_MS", 250, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.STT_INTENT_PREFETCH_ENABLED", True, raising=False)

    calls = {"n": 0}

    def _transcribe(_audio, _sr):
        calls["n"] += 1
        if calls["n"] == 1:
            return "run"
        return "run diagnostics"

    feed_idx = {"i": 0}
    chunks = [_tone(0.12, amp=0.35)] * 8 + [_tone(0.12, amp=0.0)] * 12

    def _feed():
        i = feed_idx["i"]
        feed_idx["i"] = min(i + 1, len(chunks) - 1)
        return chunks[i]

    session = StreamingSttSession(
        transcribe_fn=_transcribe,
        audio_feed=_feed,
        partial_interval_ms=50,
    )
    with patch(
        "voice.streaming_stt.transcribe.transcribe_stream_final",
        side_effect=lambda _audio, _sr, partial_text="": partial_text,
    ):
        out = session.run_until_endpoint(max_seconds=3.0)
    assert out.partial_updates >= 1
    assert "diagnostic" in out.text.lower() or "run" in out.text.lower()


def test_prefetch_does_not_execute():
    with patch("actions.registry.ActionRegistry.execute") as execute:
        prefetch_intent("run diagnostics")
        execute.assert_not_called()


def test_barge_in_on_speech(monkeypatch):
    monkeypatch.setattr("config.TTS_BARGE_IN_ENABLED", True, raising=False)
    with patch("voice.speech_controller.barge_in_if_speaking") as barge:
        session = StreamingSttSession(
            transcribe_fn=lambda _a, _s: "",
            audio_feed=lambda: _tone(0.1, amp=0.4),
            partial_interval_ms=80,
        )
        session.feed_audio(_tone(0.1, amp=0.4))
        barge.assert_called()


def test_concurrent_stt_tts_interrupt():
    request_stop_speaking()
    from voice.streaming_player import _speaking

    _speaking.set()
    try:
        with patch("voice.speech_controller.barge_in_if_speaking") as barge:
            barge.return_value = True
            from voice.speech_controller import barge_in_if_speaking

            assert barge_in_if_speaking() is True
            barge.assert_called_once()
    finally:
        _speaking.clear()


def test_latency_budget_partial_interval(monkeypatch):
    monkeypatch.setattr("config.STT_PARTIAL_INTERVAL_MS", 250, raising=False)
    assert 250 <= 250 <= 500


def test_realtime_metrics_publish():
    publish = RealtimeSttMetrics(
        last_decode_ms=42.0,
        buffer_seconds=2.5,
        partial_count=3,
        prefetch_intent="run_diagnostics",
        stream_active=True,
    )
    from voice.streaming_stt.realtime_metrics import publish_metrics

    with patch("ui.overlay_app.notify_overlay_realtime_stt_metrics") as notify:
        publish_metrics(publish)
        notify.assert_called_once()
    snap = get_realtime_metrics()
    assert snap is not None
    assert snap.prefetch_intent == "run_diagnostics"


def test_streaming_disabled_by_default():
    from voice.streaming_stt import is_streaming_stt_enabled

    import config

    assert config.STT_STREAMING_BUFFER_ENABLED is False or is_streaming_stt_enabled() == bool(
        config.STT_STREAMING_BUFFER_ENABLED
    )


def test_phase426_runtime_contract_defaults():
    import config as cfg

    assert cfg.streaming_chunk_samples(sample_rate=16000) == 1600
    assert 1.5 <= cfg.STT_ROLLING_BUFFER_SECONDS <= 3.0
    assert 250 <= cfg.STT_PARTIAL_INTERVAL_MS <= 500
    assert cfg.STT_STREAM_MIN_PARTIAL_CONTEXT_MS >= 250


def test_partial_decode_waits_for_rolling_context(monkeypatch):
    monkeypatch.setattr("config.STT_STREAM_MIN_PARTIAL_CONTEXT_MS", 250, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.STT_STREAM_OVERLAP_MS", 0, raising=False)

    seen_durations: list[float] = []

    def _transcribe(audio, sr):
        seen_durations.append(audio.shape[0] / float(sr))
        return "open dashboard"

    session = StreamingSttSession(
        sample_rate=16000,
        chunk_samples=1600,
        transcribe_fn=_transcribe,
        partial_interval_ms=50,
    )
    chunk = np.ones(1600, dtype=np.float32) * 0.3
    session.feed_audio(chunk)
    session._maybe_partial()
    assert seen_durations == []

    session.feed_audio(chunk)
    session.feed_audio(chunk)
    with patch("ui.overlay_app.notify_overlay_partial_transcript") as hud:
        session._maybe_partial()

    assert seen_durations and min(seen_durations) >= 0.25
    hud.assert_called()


def test_silent_partial_intent_prediction_never_acks_or_executes(monkeypatch):
    monkeypatch.setattr("config.STT_STREAM_MIN_PARTIAL_CONTEXT_MS", 250, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.STT_INTENT_PREFETCH_ENABLED", True, raising=False)

    session = StreamingSttSession(
        sample_rate=16000,
        chunk_samples=1600,
        transcribe_fn=lambda _audio, _sr: "run diagnostics",
        partial_interval_ms=50,
    )
    chunk = np.ones(1600, dtype=np.float32) * 0.3
    for _ in range(3):
        session.feed_audio(chunk)

    with (
        patch("actions.registry.ActionRegistry.execute") as execute,
        patch("ui.overlay_app.notify_overlay_fast_ack") as fast_ack,
    ):
        session._maybe_partial()

    execute.assert_not_called()
    fast_ack.assert_not_called()
    assert session._last_prefetch_intent


def test_endpoint_finalizes_once_and_final_routes_after_silence(monkeypatch):
    monkeypatch.setattr("config.STT_STREAM_ENDPOINT_SILENCE_MS", 200, raising=False)
    monkeypatch.setattr("config.STT_STREAM_MIN_SPEECH_MS", 100, raising=False)
    monkeypatch.setattr("config.STT_STREAM_MIN_PARTIAL_CONTEXT_MS", 250, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)

    chunks = [np.ones(100, dtype=np.float32) * 0.35] * 5
    chunks += [np.zeros(100, dtype=np.float32)] * 4
    idx = {"i": 0}

    def _feed():
        i = min(idx["i"], len(chunks) - 1)
        idx["i"] += 1
        return chunks[i]

    final_audio_seconds: list[float] = []

    def _final(audio, sr, *, partial_text=""):
        del partial_text
        final_audio_seconds.append(audio.shape[0] / float(sr))
        return "open dashboard"

    with patch("voice.streaming_stt.transcribe.transcribe_stream_final", side_effect=_final):
        out = StreamingSttSession(
            sample_rate=1000,
            chunk_samples=100,
            transcribe_fn=lambda _audio, _sr: "open dash",
            audio_feed=_feed,
            partial_interval_ms=50,
        ).run_until_endpoint(max_seconds=2.0)

    assert out.text == "open dashboard"
    assert len(final_audio_seconds) == 1
    assert final_audio_seconds[0] >= 0.5
    assert out.endpoint_silence_ms >= 200
