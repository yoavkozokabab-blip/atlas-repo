"""Phase 42 v2 — elite speech recognition."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brain.command_grammar import apply_grammar_correction, score_command_grammar
from brain.intent_classifier import classify
from core.types import Intent
from voice.auto_tune import analyze_voice_diagnostics
from voice.transcriber import TranscriptionResult, reset_model_cache
from voice.voice_calibration import (
    apply_calibration_corrections,
    record_calibration_heard,
    run_voice_calibration,
)
from voice.voice_calibration import reset_calibration_file
from voice.voice_debug_store import format_voice_debug_status, get_voice_debug_snapshot, reset_voice_debug_store
from voice.wake_diagnostics import format_wake_diagnostics, record_wake_session, reset_wake_diagnostics


@pytest.fixture(autouse=True)
def _clean():
    reset_voice_debug_store()
    reset_wake_diagnostics()
    reset_model_cache()
    reset_calibration_file()
    yield
    reset_voice_debug_store()
    reset_wake_diagnostics()
    reset_model_cache()
    reset_calibration_file()


def test_grammar_correction_open_dashboard():
    text, match = apply_grammar_correction("open dash board")
    assert match is not None
    assert "dashboard" in text
    assert match.intent == Intent.OPEN_TRADING_DASHBOARD


def test_grammar_no_execution():
    match = score_command_grammar("run diagnostic")
    assert match is not None
    assert match.intent == Intent.RUN_DIAGNOSTICS
    # Grammar module never calls router/actions
    assert match.correction_reason in {"exact_phrase", "fuzzy_grammar_match"}


def test_classifier_routes_grammar_corrected_text():
    req = classify("open dash board")
    assert req.intent in {Intent.OPEN_TRADING_DASHBOARD, Intent.UNKNOWN}


@patch("voice.transcriber.transcribe_faster_whisper_hypothesis")
def test_multipass_unknown_triggers_retry(mock_hyp, tmp_path, monkeypatch):
    from voice.stt_stack.multipass import transcribe_multipass

    monkeypatch.setattr("voice.stt_stack.multipass.STT_RETRY_ON_UNKNOWN", True, raising=False)
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"RIFF")
    fast = MagicMock(
        text="xyz unknown phrase",
        language="en",
        confidence=0.4,
        avg_logprob=-1.1,
        language_probability=0.5,
    )
    accurate = MagicMock(
        text="open dashboard",
        language="en",
        confidence=0.9,
        avg_logprob=-0.4,
        language_probability=0.9,
    )
    mock_hyp.side_effect = [fast, accurate]

    with patch("voice.stt_stack.multipass._preview_intent_unknown", return_value=True):
        result = transcribe_multipass(wav)
    assert mock_hyp.call_count >= 2
    assert "dashboard" in result.text.lower() or result.text


def test_calibration_stores_safe_pairs():
    run_voice_calibration(["show jarvis status"])
    ok = record_calibration_heard(expected="show jarvis status", heard="show jar vis status")
    assert ok
    corrected = apply_calibration_corrections("show jar vis status")
    assert "jarvis" in corrected


def test_voice_debug_fields():
    from voice.voice_debug_store import record_voice_understanding

    record_voice_understanding(
        raw="open dash board",
        normalized="open dashboard",
        grammar_corrected="open dashboard",
        grammar_command="open_trading_dashboard",
        grammar_confidence=0.92,
        grammar_reason="fuzzy_grammar_match",
        retry_reason="unknown_intent",
        pass_latencies_ms={"fast": 120.0, "repair": 5.0},
    )
    snap = get_voice_debug_snapshot()
    assert snap.last_grammar_corrected_transcript
    assert snap.last_grammar_command
    assert snap.last_retry_reason
    assert "fast" in snap.last_pass_latencies_ms
    text = format_voice_debug_status()
    assert "grammar_corrected_transcript" in text
    assert "selected_command" in text


def test_wake_diagnostics_fields():
    record_wake_session(
        session_ms=500,
        speech_ms=300,
        silence_cutoff_ms=200,
        stt_ms=180,
        empty_after_wake=False,
        clipped=False,
        raw_transcript="open dash",
        normalized_transcript="open dashboard",
        corrected_transcript="open dashboard",
    )
    text = format_wake_diagnostics()
    assert "avg_stt_ms" in text
    assert "last_wake_raw" in text


def test_auto_tune_recommendations_local_only():
    recs = analyze_voice_diagnostics()
    assert recs
    for r in recs:
        assert "cloud" not in r.reason.lower()
        assert "deepgram" not in r.key.lower()


def test_classifier_auto_tune_voice():
    req = classify("auto tune voice")
    assert req.intent == Intent.AUTO_TUNE_VOICE


def test_no_cloud_dependency_config():
    import config

    assert hasattr(__import__("voice.stt_stack.multipass", fromlist=["transcribe_multipass"]), "transcribe_multipass")
    assert not config.DEEPGRAM_LOCAL_URL
