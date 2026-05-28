"""Phase 41 — premium voice stack."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from brain.intent_classifier import classify
from core.types import Intent
from voice.emotion_modes import get_emotion_preset
from voice.engines.registry import get_engine, list_registered_engines
from voice.viseme_timeline import build_viseme_frames
from voice.voice_stack_store import (
    load_voice_profile,
    reset_voice_profile_file,
    save_voice_profile,
    set_female_voice,
    VoiceStackProfile,
)


@pytest.fixture(autouse=True)
def _clean_voice_stack():
    reset_voice_profile_file()
    yield
    reset_voice_profile_file()


def test_emotion_presets_female_neural():
    preset = get_emotion_preset("cinematic")
    assert preset is not None
    assert "Neural" in preset.edge_voice or "Aria" in preset.edge_voice


def test_viseme_timeline_non_empty():
    frames = build_viseme_frames("open dashboard and run diagnostics")
    assert len(frames) >= 3
    assert max(frames) <= 1.0


def test_engine_registry_includes_core_engines():
    names = list_registered_engines()
    assert "edge_tts" in names
    assert "pyttsx3" in names
    assert get_engine("edge_tts") is not None


def test_set_female_voice_persists():
    prof = set_female_voice()
    assert "Jenny" in prof.voice or "Aria" in prof.voice
    loaded = load_voice_profile()
    assert loaded.engine == "edge_tts"


def test_classifier_list_voices():
    req = classify("list voices")
    assert req.intent == Intent.LIST_VOICES


def test_classifier_set_cinematic():
    req = classify("set cinematic voice")
    assert req.intent == Intent.SET_CINEMATIC_VOICE


@patch("voice.tts.TTSService.speak")
def test_stop_speaking_action(mock_speak):
    from actions.voice_stack_actions import StopSpeakingAction
    from core.types import CommandRequest

    result = StopSpeakingAction().execute(
        CommandRequest(raw_text="stop speaking", intent=Intent.STOP_SPEAKING)
    )
    assert result.status.value == "success"


def test_tts_benchmark_report():
    from voice.tts_benchmark import run_tts_benchmark

    report = run_tts_benchmark(phrase="test")
    assert "TTS benchmark" in report
    assert "edge_tts" in report


def test_voice_profile_roundtrip():
    prof = VoiceStackProfile(voice="en-US-JennyNeural", emotion="calm", engine="edge_tts")
    save_voice_profile(prof)
    loaded = load_voice_profile()
    assert loaded.voice == "en-US-JennyNeural"
    assert loaded.emotion == "calm"
