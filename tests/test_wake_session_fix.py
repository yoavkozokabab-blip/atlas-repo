"""Minimal wake-session fixes — silence-stop, empty transcript, command path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState, get_runtime_state, reset_runtime_state
from ui.overlay_app import get_overlay_controller, reset_overlay_controller
from ui.overlay_state import OverlayPhase
from voice.microphone import record_for_seconds
from voice.transcriber import TranscriptionResult
from voice.stt_empty_guidance import PRIMARY_EMPTY_WAKE_MSG
from voice.wakeword_loop import run_post_wake_listening_session


def _stt(text: str, *, low: bool = False) -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="en",
        model="medium",
        device="cpu",
        compute_type="int8",
        low_confidence=low,
    )


@pytest.fixture
def app():
    reset_runtime_state()
    reset_overlay_controller()
    return JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))


def test_wake_session_uses_guarded_early_stop(monkeypatch, tmp_path):
    """wake_session=True may stop on silence only after speech has been heard."""
    monkeypatch.setattr("voice.microphone.silence_stop_enabled", lambda: True)
    monkeypatch.setattr("voice.microphone.wake_early_stop_enabled", lambda: True)
    captured: list[tuple[bool, bool]] = []

    def fake_record_stream(
        *,
        silence_stop: bool = False,
        require_voice_before_silence_stop: bool = False,
        **kwargs,
    ):
        captured.append((silence_stop, require_voice_before_silence_stop))
        return np.ones(1600, dtype=np.float32) * 0.1

    out = tmp_path / "out.wav"
    monkeypatch.setattr("voice.microphone._record_stream", fake_record_stream)
    monkeypatch.setattr("voice.microphone._save_wav", lambda _a, _r: out)
    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr("voice.microphone._resolve_device", lambda: None)

    record_for_seconds(3.0, wake_session=True)
    record_for_seconds(3.0, wake_session=False)

    assert captured == [(True, True), (True, True)]


def test_empty_stripped_transcript_shows_overlay_error(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    errors: list[str] = []

    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_listening", lambda: None)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: _stt("hey jarvis"),
    )
    monkeypatch.setattr(
        "ui.overlay_app.notify_overlay_error",
        lambda msg: errors.append(msg),
    )
    with patch("voice.voice_loop.process_voice_transcript") as proc:
        run_post_wake_listening_session(app)
    proc.assert_not_called()
    assert errors and PRIMARY_EMPTY_WAKE_MSG in errors[0]


def test_wake_path_reaches_handle_text_command_on_valid_transcript(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    called: list[tuple] = []

    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_listening", lambda: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcribing", lambda: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcript", lambda _t: None)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_thinking", lambda: None)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: _stt("hey jarvis open dashboard"),
    )

    def _capture(app_obj, text, **kwargs):
        called.append((text, kwargs.get("input_mode"), kwargs.get("source")))

    monkeypatch.setattr("voice.wakeword_loop.process_voice_transcript", _capture)
    run_post_wake_listening_session(app)
    assert len(called) == 1
    assert called[0][0] == "open dashboard"
    assert called[0][2] == "wakeword"


def test_overlay_schedules_hide_after_empty_wake_transcript(app, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"RIFF")
    rt = get_runtime_state()
    rt.set_overlay(True)
    ctrl = get_overlay_controller()
    ctrl.set_enabled(True, runtime=rt)

    monkeypatch.setattr("voice.wake_greeting.play_wake_greeting_async", lambda _a: False)
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: _stt("hey jarvis"),
    )

    run_post_wake_listening_session(app)

    snap = ctrl._state.snapshot()
    assert snap.phase == OverlayPhase.ERROR
    assert PRIMARY_EMPTY_WAKE_MSG in snap.error_message
    assert snap.hide_after_monotonic is not None
