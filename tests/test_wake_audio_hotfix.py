"""Wake clipping + audio routing hotfix tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ui.overlay_state import OverlayPhase, OverlayState
from voice.fast_voice import (
    effective_wake_post_speech_buffer_ms,
    effective_wake_silence_seconds,
)
from voice.spoken_normalization import normalize_spoken_command
from voice.wake_diagnostics import (
    estimate_clipped_session,
    format_wake_diagnostics,
    record_wake_session,
    reset_wake_diagnostics,
    snapshot,
)
from voice.wake_greeting import strip_wake_phrase_from_transcript
from voice.wake_phrases import wake_listen_prompt


def test_wake_post_speech_buffer_default(monkeypatch):
    monkeypatch.setattr("config.WAKE_POST_SPEECH_BUFFER_MS", 700, raising=False)
    assert effective_wake_post_speech_buffer_ms() == 700.0


def test_wake_silence_default_less_aggressive(monkeypatch):
    monkeypatch.setattr("config.WAKE_SILENCE_SECONDS", 1.6, raising=False)
    assert effective_wake_silence_seconds() >= 1.5


def test_wake_record_passes_tail_buffer_to_stream(monkeypatch, tmp_path):
    captured: dict = {}

    def fake_stream(**kwargs):
        captured.update(kwargs)
        return np.ones(8000, dtype=np.float32) * 0.1

    monkeypatch.setattr("voice.microphone._record_stream", fake_stream)
    monkeypatch.setattr("voice.microphone._save_wav", lambda a, r: tmp_path / "w.wav")
    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr("voice.microphone._resolve_device", lambda: None)
    monkeypatch.setattr("voice.microphone.wake_early_stop_enabled", lambda: True)

    from voice.microphone import record_for_seconds

    record_for_seconds(2.0, wake_session=True)
    assert captured.get("post_speech_buffer_ms") == 700.0
    assert captured.get("require_voice_before_silence_stop") is True
    assert captured.get("min_speech_seconds", 0) > 0


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("describe the screener", "describe the screen"),
        ("read the screener", "read the screen"),
        ("analyze the screener", "analyze the screen"),
    ],
)
def test_screener_normalization(raw: str, expected: str) -> None:
    assert normalize_spoken_command(raw) == expected


def test_wake_diagnostics_and_clipped_estimate():
    reset_wake_diagnostics()
    record_wake_session(
        session_ms=1200,
        speech_ms=200,
        silence_cutoff_ms=1000,
        empty_after_wake=True,
        clipped=True,
    )
    s = snapshot()
    assert s.session_count == 1
    assert s.clipped_session_count == 1
    assert s.empty_after_wake_count == 1
    text = format_wake_diagnostics()
    assert "wake_detected_count" in text
    assert estimate_clipped_session(
        raw_text="hey jarvis",
        normalized_text="",
        speech_ms=100,
        empty_after_wake=True,
        min_command_speech_ms=450,
    )


def test_show_wake_diagnostics_action():
    from actions.voice_audio_actions import ShowWakeDiagnosticsAction
    from core.types import CommandRequest, Intent

    result = ShowWakeDiagnosticsAction().execute(
        CommandRequest(raw_text="show wake diagnostics", intent=Intent.SHOW_WAKE_DIAGNOSTICS.value)
    )
    assert result.status.value == "success"
    assert "Wake diagnostics" in result.summary


def test_audio_devices_report_lists_default():
    from voice.audio_devices import format_audio_devices_report

    text = format_audio_devices_report()
    assert "Audio devices" in text
    assert "Windows playback" in text


def test_cycle_audio_output_selects_session_device(monkeypatch):
    from voice import audio_devices
    from voice import audio_routing
    from voice.audio_routing import cycle_audio_output

    audio_routing._CYCLE_INDEX = 0
    audio_devices.set_session_output_device(None)
    monkeypatch.setattr(
        "voice.audio_routing.list_playback_devices",
        lambda: [
            audio_devices.PlaybackDeviceInfo(0, "Speakers", "MME", True),
            audio_devices.PlaybackDeviceInfo(1, "SteelSeries", "WASAPI", False),
        ],
    )
    monkeypatch.setattr("voice.audio_routing._play_tone", lambda **k: None)
    monkeypatch.setattr(
        "voice.audio_routing.TTSService",
        lambda **k: MagicMock(speak=lambda _t: True),
    )
    result = cycle_audio_output()
    assert result.ok
    assert audio_devices.get_session_output_device() == 0


def test_quiet_mode_overlay_unchanged():
    state = OverlayState()
    state.set_ready(quiet=True)
    assert state.snapshot().quiet_ready is True
    state.set_ready(quiet=False)
    assert state.snapshot().phase == OverlayPhase.READY


def test_startup_prompt_includes_both_wake_phrases():
    prompt = wake_listen_prompt()
    assert "Jarvis" in prompt and "Hey Jarvis" in prompt
