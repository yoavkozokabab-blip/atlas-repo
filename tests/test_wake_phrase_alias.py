"""Wake phrase alias: Jarvis + Hey Jarvis UX and transcript strip."""

from __future__ import annotations

from voice.wake_greeting import strip_wake_phrase_from_transcript
from voice.wake_phrases import parse_wake_display_phrases, wake_listen_prompt
from voice.wakeword import format_wake_word_model_status, resolve_oww_model_name


def test_strip_wake_phrase_removes_jarvis():
    assert strip_wake_phrase_from_transcript("Jarvis") == ""
    assert strip_wake_phrase_from_transcript("Jarvis open dashboard") == "open dashboard"


def test_strip_wake_phrase_removes_hey_jarvis():
    assert strip_wake_phrase_from_transcript("Hey Jarvis") == ""
    assert strip_wake_phrase_from_transcript("Hey Jarvis open dashboard") == "open dashboard"
    assert strip_wake_phrase_from_transcript("Hey Jarvis, open dashboard") == "open dashboard"
    assert strip_wake_phrase_from_transcript("Hey Jarvis!") == ""


def test_startup_display_includes_both_phrases(monkeypatch):
    monkeypatch.setattr(
        "config.WAKE_WORD_DISPLAY_PHRASES",
        "Jarvis, Hey Jarvis",
        raising=False,
    )
    prompt = wake_listen_prompt()
    assert "Jarvis" in prompt
    assert "Hey Jarvis" in prompt
    assert "or" in prompt


def test_wake_display_phrases_config_default():
    phrases = parse_wake_display_phrases("Jarvis, Hey Jarvis")
    assert phrases == ("Jarvis", "Hey Jarvis")


def test_jarvis_model_alias_resolves_to_hey_jarvis():
    assert resolve_oww_model_name("jarvis") == "hey_jarvis"
    assert resolve_oww_model_name("hey_jarvis") == "hey_jarvis"


def test_model_status_documents_trained_phrase(monkeypatch, tmp_path):
    onnx = tmp_path / "hey_jarvis.onnx"
    onnx.write_bytes(b"fake")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL_PATH", str(onnx))
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_MODEL", "jarvis")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_DISPLAY_PHRASES", "Jarvis, Hey Jarvis")
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_THRESHOLD", 0.6)

    from voice.wakeword import resolve_wake_word_model

    res = resolve_wake_word_model()
    text = format_wake_word_model_status(res)
    assert "hey_jarvis" in text
    assert "Hey Jarvis" in text
    assert "Jarvis, Hey Jarvis" in text
    assert "Detection threshold: 0.6" in text
