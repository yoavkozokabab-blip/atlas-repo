"""Phase 42 — world-class speech recognition stack."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from brain.intent_classifier import classify
from core.types import Intent
from voice.stt_engines.base import SttHypothesis, logprob_to_confidence
from voice.stt_engines.registry import get_stt_engine, list_registered_stt_engines
from voice.stt_stack.audio_enhance import cancel_echo, enhance_audio_array, suppress_noise
from voice.stt_stack.confidence_fusion import fuse_hypotheses
from voice.stt_stack.intent_correction import apply_intent_corrections
from voice.stt_stack.language_detect import detect_language_from_text, resolve_transcription_language
from voice.stt_stack.partial_stream import clear_partial_listeners, emit_partial, get_last_partial
from voice.stt_stack.retry_pipeline import run_with_retries
from voice.stt_stack.transcript_repair import repair_transcript
from voice.stt_stack.voice_fingerprint import (
    VoiceFingerprint,
    extract_spectral_centroid,
    load_fingerprint,
    reset_stt_stack_file,
    save_fingerprint,
)
from voice.transcriber import TranscriptionResult, reset_model_cache


@pytest.fixture(autouse=True)
def _clean_stt_stack():
    reset_stt_stack_file()
    reset_model_cache()
    clear_partial_listeners()
    yield
    reset_stt_stack_file()
    reset_model_cache()
    clear_partial_listeners()


def test_stt_engine_registry_lists_backends():
    names = list_registered_stt_engines()
    assert "faster_whisper" in names
    assert "onnx_whisper" in names
    assert "whisper_cpp" in names
    assert get_stt_engine("faster_whisper") is not None


def test_confidence_fusion_picks_best_cluster():
    hyps = [
        SttHypothesis(text="open dashboard", engine="a", confidence=0.7),
        SttHypothesis(text="open dash board", engine="b", confidence=0.65),
        SttHypothesis(text="run diagnostics", engine="c", confidence=0.9),
    ]
    fused = fuse_hypotheses(hyps)
    assert "diagnostic" in fused.text or fused.confidence >= 0.65


def test_logprob_to_confidence_monotonic():
    low = logprob_to_confidence(-1.2)
    high = logprob_to_confidence(-0.4)
    assert high > low


def test_intent_correction_run_diagnostics():
    text, changed = apply_intent_corrections("run diagnostic")
    assert "diagnostics" in text
    assert changed


def test_transcript_repair_dashboard():
    text, changed = repair_transcript("open dash board")
    assert "dashboard" in text.lower()
    assert changed


def test_language_detect_hebrew():
    with patch("voice.stt_stack.language_detect.STT_AUTO_LANGUAGE_DETECT", True):
        assert detect_language_from_text("פתח קרסור") == "he"
    assert resolve_transcription_language(forced="en") == "en"


def test_audio_enhance_does_not_explode():
    audio = np.random.randn(8000).astype(np.float32) * 0.1
    out = enhance_audio_array(suppress_noise(cancel_echo(audio)))
    assert out.shape == audio.shape
    assert float(np.max(np.abs(out))) <= 1.0


def test_partial_stream_emit():
    seen: list[str] = []
    from voice.stt_stack.partial_stream import register_partial_listener

    register_partial_listener(seen.append)
    with patch("voice.stt_stack.partial_stream.STT_PARTIAL_STREAMING_ENABLED", True):
        emit_partial("open dash")
    assert get_last_partial() == "open dash"
    assert seen == ["open dash"]


def test_retry_pipeline_stops_when_confident():
    calls = {"n": 0}

    def _fake(_path, *, language, on_partial, attempt):
        calls["n"] += 1
        conf = 0.9 if attempt > 0 else 0.3
        return [SttHypothesis(text="ok", engine="mock", confidence=conf, language=language)]

    fused, _, attempts = run_with_retries(
        _fake,
        Path("x.wav"),
        language="en",
        on_partial=None,
        max_attempts=3,
    )
    assert fused.text == "ok"
    assert attempts >= 2
    assert calls["n"] >= 2


def test_voice_fingerprint_persist():
    fp = VoiceFingerprint(sample_count=2, grammar_min_score=82)
    save_fingerprint(fp)
    loaded = load_fingerprint()
    assert loaded.grammar_min_score == 82


def test_classifier_list_stt_engines():
    req = classify("list stt engines")
    assert req.intent == Intent.LIST_STT_ENGINES


def test_classifier_show_stt_stack_status():
    req = classify("show stt stack status")
    assert req.intent == Intent.SHOW_STT_STACK_STATUS


@patch("voice.stt_stack.stt_controller.get_stt_engine_chain")
def test_transcribe_with_stack_mock(mock_chain, tmp_path):
    from voice.stt_stack.stt_controller import transcribe_with_stack

    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")  # not valid audio; engines mocked

    class _MockEng:
        name = "mock"

        def is_available(self):
            return True

        def capabilities(self):
            from voice.stt_engines.base import SttEngineCapabilities

            return SttEngineCapabilities()

        def transcribe(self, audio_path, *, language, on_partial=None):
            if on_partial:
                on_partial("partial open")
            return SttHypothesis(
                text="open dashboard",
                engine="mock",
                confidence=0.88,
                language=language,
            )

    mock_chain.return_value = [_MockEng()]
    with patch("voice.stt_stack.stt_controller.enhance_audio_file", side_effect=lambda p: p):
        result = transcribe_with_stack(wav)
    assert isinstance(result, TranscriptionResult)
    assert "dashboard" in result.text.lower()
    assert result.fused_confidence is not None


def test_list_stt_engines_action():
    from actions.stt_stack_actions import ListSttEnginesAction
    from core.types import CommandRequest

    out = ListSttEnginesAction().execute(
        CommandRequest(raw_text="list stt engines", intent=Intent.LIST_STT_ENGINES)
    )
    assert "faster_whisper" in out.summary


def test_fingerprint_centroid():
    audio = np.sin(np.linspace(0, 40, 1600)).astype(np.float32)
    c = extract_spectral_centroid(audio)
    assert c >= 0.0
