"""English-first STT defaults, phrase mappings, and transcription tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from brain.intent_classifier import classify_rules
from core.types import Intent


@pytest.fixture(autouse=True)
def _reset_stt_cache():
    from voice.transcriber import reset_model_cache

    reset_model_cache()
    yield
    reset_model_cache()


def test_resolve_stt_language_defaults_to_en(monkeypatch):
    from voice.stt_config import resolve_stt_language

    monkeypatch.delenv("STT_LANGUAGE", raising=False)
    assert resolve_stt_language(None) == "en"
    assert resolve_stt_language("") == "en"
    assert resolve_stt_language("auto") == "en"


def test_resolve_stt_language_hebrew_not_auto_from_locale(monkeypatch):
    from voice.stt_config import resolve_stt_language

    monkeypatch.delenv("STT_LANGUAGE", raising=False)
    # Even on Hebrew locale, unset STT_LANGUAGE must stay English
    assert resolve_stt_language(None) == "en"


def test_resolve_stt_language_explicit_he(monkeypatch):
    from voice.stt_config import resolve_stt_language

    assert resolve_stt_language("he") == "he"


def test_resolve_stt_language_invalid_falls_back_to_en():
    from voice.stt_config import resolve_stt_language

    assert resolve_stt_language("fr") == "en"


def test_config_stt_language_default_en(monkeypatch):
    monkeypatch.delenv("STT_LANGUAGE", raising=False)
    import importlib

    import config

    importlib.reload(config)
    assert config.STT_LANGUAGE == "en"


@pytest.mark.parametrize(
    "phrase,expected_intent,expected_workflow",
    [
        ("open dashboard", Intent.OPEN_TRADING_DASHBOARD, None),
        ("open the dashboard", Intent.OPEN_TRADING_DASHBOARD, None),
        ("show dashboard", Intent.OPEN_TRADING_DASHBOARD, None),
        ("open dashboard url", Intent.OPEN_TRADING_DASHBOARD_URL, None),
        ("check the dashboard", Intent.SHOW_DASHBOARD_HEALTH, None),
        ("is the dashboard running", Intent.SHOW_DASHBOARD_HEALTH, None),
        ("run a system check", Intent.RUN_DIAGNOSTICS, None),
        ("what is wrong", Intent.RUN_DIAGNOSTICS, None),
        ("check trading", Intent.RUN_WORKFLOW, "trading_health_check"),
        ("check my trading system", Intent.RUN_WORKFLOW, "trading_health_check"),
        ("show me the errors", Intent.SHOW_LAST_ERRORS, None),
        ("what can you do", Intent.SHOW_CAPABILITIES, None),
        ("show voice status", Intent.SHOW_STT_STATUS, None),
        ("show speech status", Intent.SHOW_STT_STATUS, None),
    ],
)
def test_english_voice_phrase_mappings(phrase, expected_intent, expected_workflow):
    req = classify_rules(phrase)
    assert req.intent == expected_intent
    if expected_workflow:
        assert req.params.get("workflow") == expected_workflow


def test_show_stt_status_reports_language_en(monkeypatch):
    monkeypatch.setattr("voice.transcriber.STT_LANGUAGE", "en")
    from actions.stt_actions import ShowSttStatusAction

    result = ShowSttStatusAction().execute(
        MagicMock(intent=Intent.SHOW_STT_STATUS, raw_text="show stt status")
    )
    assert "Language: en" in result.summary


def test_faster_whisper_forces_english_language(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")

    monkeypatch.setattr("voice.transcriber.STT_LANGUAGE", "en")
    monkeypatch.setattr("config.STT_ENGINE", "faster_whisper")
    monkeypatch.setattr("config.STT_MODEL", "base")
    monkeypatch.setattr("config.STT_ENABLE_NORMALIZATION", True)
    import config

    expected_beam = config.STT_BEAM_SIZE

    class FakeSeg:
        text = "open dashboard"
        avg_logprob = -0.3

    class FakeInfo:
        language_probability = 0.95
        duration = 1.2

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            assert kwargs.get("language") == "en"
            assert kwargs.get("beam_size") == expected_beam
            assert kwargs.get("condition_on_previous_text") is False
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
    assert result.text == "open dashboard"
    assert result.language == "en"
