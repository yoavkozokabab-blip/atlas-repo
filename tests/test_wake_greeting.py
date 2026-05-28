"""Wake greeting and transcript filtering tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState, reset_runtime_state


@pytest.fixture
def app():
    reset_runtime_state()
    return JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))
from voice.wake_greeting import (
    format_wake_greeting,
    play_wake_greeting,
    strip_wake_phrase_from_transcript,
)


def test_format_wake_greeting_uses_config_name(monkeypatch):
    monkeypatch.setattr("voice.wake_greeting.JARVIS_USER_NAME", "Yoav")
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_TEXT", "Hey {name}")
    assert format_wake_greeting() == "Hey Yoav"


def test_play_wake_greeting_speaks_when_enabled(monkeypatch):
    runtime = RuntimeState(speak_enabled=True)
    app = JarvisApp(speak_enabled=True, runtime=runtime)
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_ENABLED", True)
    monkeypatch.setattr("voice.wake_greeting.JARVIS_USER_NAME", "Yoav")
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_TEXT", "Hey {name}")

    with patch.object(app.tts, "speak", return_value=True) as speak:
        assert play_wake_greeting(app) is True
    speak.assert_called_once_with("Hey Yoav")


def test_play_wake_greeting_disabled(monkeypatch):
    app = JarvisApp(speak_enabled=True)
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_ENABLED", False)
    with patch.object(app.tts, "speak") as speak:
        assert play_wake_greeting(app) is False
    speak.assert_not_called()


def test_play_wake_greeting_requires_tts_enabled(monkeypatch):
    app = JarvisApp(speak_enabled=False)
    monkeypatch.setattr("voice.wake_greeting.WAKE_GREETING_ENABLED", True)
    with patch.object(app.tts, "speak") as speak:
        assert play_wake_greeting(app) is False
    speak.assert_not_called()


def test_strip_wake_phrase_from_transcript():
    assert strip_wake_phrase_from_transcript("Hey Jarvis open dashboard") == "open dashboard"
    assert strip_wake_phrase_from_transcript("hey jarvis") == ""
    assert strip_wake_phrase_from_transcript("Jarvis") == ""
    assert strip_wake_phrase_from_transcript("Jarvis show capabilities") == "show capabilities"
    assert strip_wake_phrase_from_transcript("open cursor") == "open cursor"


def test_wakeword_loop_greeting_before_listen(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    order: list[str] = []

    monkeypatch.setattr(
        "voice.wake_greeting.play_wake_greeting_async",
        lambda _a: order.append("greeting") or True,
    )
    monkeypatch.setattr(
        "ui.overlay_app.notify_overlay_listening",
        lambda: order.append("listening"),
    )
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="hey jarvis show capabilities",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr(
        "voice.wake_greeting.strip_wake_phrase_from_transcript",
        lambda t: "show capabilities" if "capabilities" in t else t,
    )
    monkeypatch.setattr(
        "ui.overlay_app.notify_overlay_transcribing",
        lambda: order.append("transcribing"),
    )
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcript", lambda _t: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_thinking", lambda: None)
    monkeypatch.setattr(
        "voice.voice_loop.process_voice_transcript",
        lambda *a, **k: order.append("command"),
    )

    from voice.wakeword_loop import run_post_wake_listening_session

    run_post_wake_listening_session(app)
    assert order[0] == "listening"
    assert order[1] == "greeting"


def test_wakeword_loop_no_command_on_wake_only_transcript(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    errors: list[str] = []
    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_listening", lambda: None)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="Hey Jarvis",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr(
        "voice.wake_greeting.strip_wake_phrase_from_transcript",
        strip_wake_phrase_from_transcript,
    )
    monkeypatch.setattr(
        "ui.overlay_app.notify_overlay_error",
        lambda msg: errors.append(msg),
    )
    with patch("voice.voice_loop.process_voice_transcript") as proc:
        from voice.stt_empty_guidance import PRIMARY_EMPTY_WAKE_MSG
        from voice.wakeword_loop import run_post_wake_listening_session

        run_post_wake_listening_session(app)
    proc.assert_not_called()
    assert errors and PRIMARY_EMPTY_WAKE_MSG in errors[0]
