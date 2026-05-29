"""STT accuracy tuning + voice reliability polish (Phase STT)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState, reset_runtime_state
from ui.overlay_app import OverlayController, reset_overlay_controller
from ui.overlay_state import OverlayPhase
from voice.fast_voice import (
    effective_wake_listen_seconds,
    effective_wake_silence_seconds,
    resolve_wake_listen_seconds,
)
from voice.microphone import _silence_stop_ready, record_for_seconds
from voice.normalization import normalize_wake_transcript
from voice.performance_status import format_voice_performance_status
from voice.stt_diagnostics import record_transcription, record_wake_retry, reset_stt_diagnostics, snapshot
from voice.stt_handling import LOW_CONFIDENCE_OVERLAY_MSG
from voice.transcriber import TranscriptionResult
from voice.transcript_cleanup import cleanup_transcript


@pytest.fixture(autouse=True)
def _reset_diag():
    reset_stt_diagnostics()
    yield
    reset_stt_diagnostics()


def test_normalize_show_job_is_status():
    assert normalize_wake_transcript("show job is status") == "show jarvis status"


def test_normalize_show_jarvis_star():
    assert normalize_wake_transcript("Show Jarvis Star") == "show jarvis status"


def test_normalize_does_not_hallucinate_unrelated():
    assert normalize_wake_transcript("open dashboard") == "open dashboard"
    assert normalize_wake_transcript("so, ciao!") == "so, ciao!"


def test_cleanup_transcript_applies_wake_normalization():
    assert cleanup_transcript("show jarvis star") == "show jarvis status"


def test_silence_stop_waits_for_voice_when_required():
    assert not _silence_stop_ready(
        silence_stop=True,
        has_chunks=True,
        sample_count=20000,
        min_samples_before_silence=5600,
        now=10.0,
        last_voice_at=9.0,
        silence_seconds=1.2,
        require_voice_before_silence_stop=True,
        voice_detected=False,
    )
    assert _silence_stop_ready(
        silence_stop=True,
        has_chunks=True,
        sample_count=20000,
        min_samples_before_silence=5600,
        now=12.0,
        last_voice_at=9.0,
        silence_seconds=1.2,
        require_voice_before_silence_stop=True,
        voice_detected=True,
    )


def test_wake_recording_uses_wake_silence_tail(monkeypatch, tmp_path):
    calls: dict[str, object] = {}
    wav = tmp_path / "wake.wav"
    monkeypatch.setattr("config.WAKE_EARLY_STOP_ENABLED", True, raising=False)
    monkeypatch.setattr("config.WAKE_SILENCE_SECONDS", 1.2, raising=False)
    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr("voice.microphone._save_wav", lambda _a, _r: wav)

    def fake_record_stream(**kwargs):
        calls.update(kwargs)
        return np.ones((10, 1), dtype=np.float32)

    monkeypatch.setattr("voice.microphone._record_stream", fake_record_stream)
    record_for_seconds(10, wake_session=True)
    assert calls["silence_seconds"] == effective_wake_silence_seconds()
    assert calls["require_voice_before_silence_stop"] is True


def test_low_confidence_wake_blocks_route(monkeypatch, tmp_path):
    reset_runtime_state()
    reset_overlay_controller()
    runtime = RuntimeState(overlay_enabled=True, wake_word_enabled=True)
    app = JarvisApp(runtime=runtime)
    ctrl = OverlayController()
    ctrl.set_enabled(True, runtime=runtime)
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")

    stt = TranscriptionResult(
        text="show jarvis star",
        language="en",
        model="medium",
        device="cpu",
        compute_type="int8",
        low_confidence=True,
    )

    monkeypatch.setattr("config.STT_LOW_CONFIDENCE_BLOCK_WAKE", True, raising=False)
    monkeypatch.setattr("voice.wakeword_loop.STT_LOW_CONFIDENCE_BLOCK_WAKE", True, raising=False)
    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    monkeypatch.setattr("voice.wakeword_loop.transcribe_audio_detailed", lambda _p: stt)
    monkeypatch.setattr("ui.overlay_app.get_overlay_controller", lambda: ctrl)
    monkeypatch.setattr("ui.overlay_app._runtime_overlay_enabled", lambda: True)

    with patch.object(app, "handle_text_command") as handle:
        from voice.wakeword_loop import run_post_wake_listening_session

        run_post_wake_listening_session(app, session_already_acquired=True)
    handle.assert_not_called()
    assert ctrl._state.snapshot().phase == OverlayPhase.ERROR
    assert LOW_CONFIDENCE_OVERLAY_MSG in ctrl._state.snapshot().error_message
    assert snapshot().wake_retry_count >= 1


def test_diagnostics_in_voice_performance_status():
    record_transcription(
        model="medium",
        duration_ms=200.0,
        low_confidence=True,
        empty=False,
    )
    record_wake_retry()
    text = format_voice_performance_status()
    assert "avg_transcribe_ms" in text
    assert "low_confidence_count: 1" in text
    assert "wake_retries: 1" in text
    assert "last_stt_model: medium" in text


def test_recommended_env_example_values():
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / ".env.example").read_text(encoding="utf-8")
    assert "STT_MODEL=small" in text
    assert "VOICE_PROFILE=balanced" in text
    assert "STT_BEAM_SIZE=3" in text
    assert "STT_SILENCE_SECONDS=1.2" in text
    assert "WAKE_MAX_LISTEN_SECONDS=5" in text
    assert "STT_LOW_CONFIDENCE_BLOCK_WAKE=false" in text


def test_effective_wake_listen_default_cap(monkeypatch):
    from conversation.human_runtime import (
        enable_human_conversational_runtime,
        reset_human_runtime_for_tests,
    )

    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.WAKE_MAX_LISTEN_SECONDS", 5.0, raising=False)
    monkeypatch.setattr("config.FAST_VOICE_MODE", False, raising=False)
    monkeypatch.setattr("config.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)
    monkeypatch.setattr("config.CONVERSATION_CONTINUOUS_MIC_ENABLED", True, raising=False)
    enable_human_conversational_runtime()
    res = resolve_wake_listen_seconds()
    assert res.wake_listen_seconds == 5.0
    assert res.mode in {"stable", "discrete"}
    assert res.source.startswith("wake_max_listen_seconds") or res.source.startswith(
        "env:WAKE_MAX_LISTEN_SECONDS"
    )


def test_conversational_session_uses_turn_max(monkeypatch):
    from conversation.human_runtime import (
        activate_session_for_tests,
        reset_human_runtime_for_tests,
    )

    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.CONVERSATION_TURN_MAX_SECONDS", 45.0, raising=False)
    activate_session_for_tests()
    res = resolve_wake_listen_seconds()
    assert res.wake_listen_seconds == 45.0
    assert res.mode == "conversational"
    assert res.source == "conversation_turn_max_seconds"


def test_wake_listen_env_override(monkeypatch):
    from conversation.human_runtime import reset_human_runtime_for_tests

    reset_human_runtime_for_tests()
    monkeypatch.setenv("WAKE_MAX_LISTEN_SECONDS", "7.5")
    monkeypatch.setattr("config.WAKE_MAX_LISTEN_SECONDS", 7.5, raising=False)
    monkeypatch.setattr("config.FAST_VOICE_MODE", False, raising=False)
    res = resolve_wake_listen_seconds()
    assert res.wake_listen_seconds == 7.5
    assert "WAKE_MAX_LISTEN_SECONDS" in res.source


def test_diagnostics_include_wake_listen_resolution():
    text = format_voice_performance_status()
    assert "wake_listen_seconds=" in text
    assert "source=" in text
    assert "mode=" in text
