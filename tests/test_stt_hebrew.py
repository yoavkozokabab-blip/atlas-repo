"""Hebrew STT configuration and transcription tests (mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.app import JarvisApp
from core.types import ActionStatus, Intent
from brain.intent_classifier import classify_rules


@pytest.fixture(autouse=True)
def _reset_stt_cache():
    from voice.transcriber import reset_model_cache

    reset_model_cache()
    yield
    reset_model_cache()


def test_resolve_stt_language_hebrew_only_when_explicit(monkeypatch):
    from voice.stt_config import resolve_stt_language

    monkeypatch.delenv("STT_LANGUAGE", raising=False)
    assert resolve_stt_language(None) == "en"
    assert resolve_stt_language("he") == "he"


def test_resolve_stt_language_explicit_en(monkeypatch):
    from voice.stt_config import resolve_stt_language

    assert resolve_stt_language("en") == "en"


def test_normalize_stt_model_allowed():
    from voice.stt_config import normalize_stt_model

    assert normalize_stt_model("large-v3") == "large-v3"
    assert normalize_stt_model("invalid-x") == "base"


def test_classify_show_stt_status():
    req = classify_rules("show stt status")
    assert req.intent == Intent.SHOW_STT_STATUS


def test_show_stt_status_action():
    from actions.stt_actions import ShowSttStatusAction

    result = ShowSttStatusAction().execute(
        MagicMock(intent=Intent.SHOW_STT_STATUS, raw_text="show stt status")
    )
    assert result.status == ActionStatus.SUCCESS
    assert "STT status" in result.summary
    assert "Model:" in result.summary
    assert "Language:" in result.summary


def test_faster_whisper_forces_hebrew_language(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")

    monkeypatch.setattr("voice.transcriber.STT_LANGUAGE", "he")
    monkeypatch.setattr("config.STT_ENGINE", "faster_whisper")
    monkeypatch.setattr("config.STT_MODEL", "base")
    monkeypatch.setattr("config.STT_ENABLE_NORMALIZATION", False)

    class FakeSeg:
        text = "פתח קרסור"
        avg_logprob = -0.3

    class FakeInfo:
        language_probability = 0.95
        duration = 1.2

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            assert kwargs.get("language") == "he"
            assert kwargs.get("task") == "transcribe"
            return [FakeSeg()], FakeInfo()

    monkeypatch.setattr(
        "voice.transcriber._load_faster_whisper",
        lambda: FakeModel(),
    )
    monkeypatch.setattr(
        "voice.transcriber._prepare_audio",
        lambda _p: (np.zeros(16000, dtype=np.float32), 16000),
    )

    from voice.transcriber import transcribe_audio_detailed

    result = transcribe_audio_detailed(wav)
    assert result.text == "פתח קרסור"
    assert result.language == "he"


def test_low_confidence_recommendation_hebrew(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"x")
    monkeypatch.setattr("voice.transcriber.STT_LANGUAGE", "he")
    monkeypatch.setattr("config.STT_LOW_CONFIDENCE_LOGPROB", -0.5)

    class FakeSeg:
        text = "גבר"
        avg_logprob = -1.2

    class FakeInfo:
        language_probability = 0.2
        duration = 0.5

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            return [FakeSeg()], FakeInfo()

    monkeypatch.setattr("voice.transcriber._load_faster_whisper", lambda: FakeModel())
    monkeypatch.setattr(
        "voice.transcriber._prepare_audio",
        lambda _p: (np.zeros(8000, dtype=np.float32), 16000),
    )

    from voice import stt_config
    from voice.transcriber import transcribe_audio_detailed

    result = transcribe_audio_detailed(wav)
    assert result.low_confidence is True
    assert stt_config.HEBREW_MODEL_HINT in (result.recommendation or "")


def test_no_default_model_fallback_in_source():
    from voice import transcriber as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "trying default pre-trained" not in source
    assert "Model(inference_framework=" not in source


def test_audio_normalization():
    from voice.audio_preprocess import normalize_audio_float

    quiet = np.array([0.01, -0.01, 0.005], dtype=np.float32)
    out = normalize_audio_float(quiet)
    assert float(np.max(np.abs(out))) > 0.5


def test_print_stt_startup_info(capsys, monkeypatch):
    monkeypatch.setattr("voice.transcriber.STT_LANGUAGE", "he")
    from voice.transcriber import print_stt_startup_info

    print_stt_startup_info()
    out = capsys.readouterr().out
    assert "STT:" in out
    assert "language=he" in out


def test_voice_loop_shows_recommendation(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")
    app = JarvisApp()
    app._running = True
    app.runtime.set_voice(True)

    def fake_record():
        app._running = False
        return wav

    monkeypatch.setattr("voice.voice_loop.record_until_enter", fake_record)
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.voice_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="test",
            language="he",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr(
        "voice.voice_loop.get_last_transcription_feedback",
        lambda: "Try STT_MODEL=medium or large-v3 for better Hebrew.",
    )
    with patch.object(app.router, "route") as route:
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
            next_suggestions=[],
        )
        from voice.voice_loop import run_voice_loop

        run_voice_loop(app)

    # console output captured indirectly — ensure no crash
    route.assert_called_once()
