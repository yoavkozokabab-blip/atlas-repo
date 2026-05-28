"""CPU baseline stabilization — no DirectML, sync pyttsx3 TTS, open dashboard smoke."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify_rules
from core.app import JarvisApp
from core.results import result_success
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import ActionStatus, Intent
from voice.latency_tracker import (
    begin_voice_command,
    finish_and_log,
    get_last_latency,
    reset_latency_tracker,
)
from voice.normalization import normalize_wake_transcript
from voice.stt_acceleration import get_stt_runtime, reset_stt_acceleration_state
from voice.wakeword_loop import run_post_wake_listening_session


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_state()
    reset_latency_tracker()
    reset_stt_acceleration_state()
    yield
    reset_runtime_state()
    reset_latency_tracker()
    reset_stt_acceleration_state()


def test_cpu_baseline_runtime_not_directml(monkeypatch):
    monkeypatch.setattr("config.STT_PREFER_DIRECTML", False, raising=False)
    monkeypatch.setattr("config.STT_DEVICE_REQUEST", "cpu", raising=False)
    from voice.stt_acceleration import configure_stt_runtime

    configure_stt_runtime(
        device_request="cpu",
        acceleration_auto=True,
        fast_profile=True,
        compute_type_override="int8",
        prefer_directml=False,
    )
    runtime = get_stt_runtime()
    assert runtime.backend == "faster_whisper"
    assert runtime.whisper_device == "cpu"
    assert runtime.acceleration == "cpu"


def test_classify_open_dashboard():
    req = classify_rules("open dashboard")
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD


def test_wake_open_dashboard_smoke(monkeypatch, tmp_path):
    """Jarvis → open dashboard: STT mock, router real, TTS sync attempted."""
    monkeypatch.setattr("config.STT_PREFER_DIRECTML", False, raising=False)
    monkeypatch.setattr("config.STT_LOW_CONFIDENCE_BLOCK_WAKE", False, raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "pyttsx3", raising=False)

    runtime = RuntimeState(speak_enabled=True, overlay_enabled=False)
    app = JarvisApp(speak_enabled=True, runtime=runtime)
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")

    from voice.transcriber import TranscriptionResult

    stt = TranscriptionResult(
        text="hey jarvis open dashboard",
        language="en",
        model="small",
        device="cpu",
        compute_type="int8",
    )

    tts_called: list[str] = []

    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_listening", lambda: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcribing", lambda: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcript", lambda _t: None)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    monkeypatch.setattr("voice.wakeword_loop.transcribe_audio_detailed", lambda _p: stt)

    with patch.object(app.tts, "speak", side_effect=lambda t: tts_called.append(t) or True):
        run_post_wake_listening_session(app, session_already_acquired=True)

    norm = normalize_wake_transcript("open dashboard")
    assert norm == "open dashboard"
    assert tts_called, "sync TTS should run after successful command"
    rec = get_last_latency()
    assert rec is not None
    assert rec.tts_ms is not None and rec.tts_ms >= 0


def test_sync_tts_records_ms_or_failure(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    app = JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))
    begin_voice_command(source="wakeword")
    with patch.object(app.tts, "speak", return_value=True):
        app._maybe_speak_result(
            result_success(Intent.OPEN_TRADING_DASHBOARD, "Opened trading dashboard.")
        )
    finish_and_log(wait_for_tts=False)
    rec = get_last_latency()
    assert rec is not None
    assert rec.tts_ms is not None
    assert rec.tts_ms >= 0
