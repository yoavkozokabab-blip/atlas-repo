"""Priority hotfix: STT normalization, aliases, voice/audio diagnostics, TTS fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent
from ui.overlay_presence import DEFAULT_IDLE_SUGGESTIONS
from ui.overlay_state import OverlayPhase, OverlayState
from voice.audio_status import format_audio_status, get_audio_status, reset_audio_status
from voice.spoken_normalization import normalize_spoken_command
from voice.tts import TTSError, TTSService
from voice.voice_debug_store import format_voice_debug_status, record_transcript_debug, reset_voice_debug_store


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("show job is status", "show jarvis status"),
        ("open trading you", "open tradingview"),
        ("open dish cord", "open discord"),
        ("open dash board", "open dashboard"),
        ("show voice debunk", "show voice debug"),
        ("run diagnostic", "run diagnostics"),
        ("what's on my screen", "describe screen"),
    ],
)
def test_spoken_normalization_coverage(raw: str, expected: str) -> None:
    assert normalize_spoken_command(raw) == expected


def test_normalization_is_deterministic_no_llm() -> None:
    a = normalize_spoken_command("show jarvis star")
    b = normalize_spoken_command("show jarvis star")
    assert a == b == "show jarvis status"


@pytest.mark.parametrize(
    "phrase,intent",
    [
        ("how are you running", Intent.SHOW_JARVIS_STATUS),
        ("what's your status", Intent.SHOW_JARVIS_STATUS),
        ("show me diagnostics", Intent.RUN_DIAGNOSTICS),
        ("show voice debug", Intent.SHOW_VOICE_DEBUG),
        ("show audio status", Intent.SHOW_AUDIO_STATUS),
        ("test voice output", Intent.TEST_VOICE_OUTPUT),
        ("open the dashboard", Intent.OPEN_TRADING_DASHBOARD),
        ("what's on my screen", Intent.DESCRIBE_SCREEN),
    ],
)
def test_intent_alias_classification(phrase: str, intent: Intent) -> None:
    req = classify_rules(phrase)
    assert req.intent == intent


def test_show_voice_debug_action():
    from actions.voice_audio_actions import ShowVoiceDebugAction

    reset_voice_debug_store()
    record_transcript_debug(raw="open dash board", normalized="open dashboard", avg_logprob=-0.4)
    result = ShowVoiceDebugAction().execute(CommandRequest(raw_text="show voice debug", intent="show_voice_debug"))
    assert result.status.value == "success"
    assert "raw_transcript" in result.summary
    assert "open dash board" in result.summary


def test_show_audio_status_action():
    from actions.voice_audio_actions import ShowAudioStatusAction

    reset_audio_status()
    with patch("voice.audio_status.get_tts_status") as mock_status:
        mock_status.return_value = MagicMock(
            enabled=True,
            engine="pyttsx3",
            async_mode=False,
            last_success=True,
            last_provider="pyttsx3",
            last_error=None,
            async_failure_count=0,
            edge_available=True,
            pyttsx_available=True,
        )
        result = ShowAudioStatusAction().execute(
            CommandRequest(raw_text="show audio status", intent="show_audio_status")
        )
    assert result.status.value == "success"
    assert "Audio status" in result.summary


def test_tts_edge_falls_back_to_pyttsx3(monkeypatch):
    monkeypatch.setattr("voice.tts.cfg.TTS_ENGINE", "edge_tts")
    svc = TTSService(enabled=True)

    def fail_edge(_safe: str) -> None:
        raise RuntimeError("edge playback failed")

    monkeypatch.setattr(svc, "_speak_edge", fail_edge)
    monkeypatch.setattr(svc, "_speak_pyttsx3", lambda _safe: None)
    monkeypatch.setattr(svc, "_notify_tts_started", lambda: None)
    monkeypatch.setattr(svc, "_notify_tts_finished", lambda: None)
    assert svc._speak_blocking("hello") is True


def test_tts_failure_shows_overlay_warning(monkeypatch):
    monkeypatch.setattr("voice.tts.cfg.TTS_ENGINE", "pyttsx3")
    svc = TTSService(enabled=True)
    warned: list[str] = []

    def capture(msg: str) -> None:
        warned.append(msg)

    monkeypatch.setattr(svc, "_speak_pyttsx3", lambda _safe: (_ for _ in ()).throw(RuntimeError("no audio")))
    monkeypatch.setattr(svc, "_overlay_tts_warning", capture)
    monkeypatch.setattr(svc, "_notify_tts_started", lambda: None)
    monkeypatch.setattr(svc, "_notify_tts_finished", lambda: None)
    with pytest.raises(TTSError):
        svc._speak_blocking("hello")
    assert warned and "TTS failed" in warned[0]


def test_overlay_ready_idle_suggestions():
    state = OverlayState()
    state.set_ready()
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.READY
    assert snap.suggestions
    assert "show jarvis status" in snap.suggestions[0] or snap.suggestions[0] == DEFAULT_IDLE_SUGGESTIONS[0]


def test_quiet_mode_overlay_unchanged():
    state = OverlayState()
    state.set_ready(quiet=True)
    snap = state.snapshot()
    assert snap.quiet_ready is True
    assert snap.phase == OverlayPhase.READY
    state.set_ready(quiet=False)
    assert state.snapshot().quiet_ready is False


def test_audio_status_format_includes_chain():
    reset_audio_status()
    text = format_audio_status()
    assert "edge_tts" in text
    assert get_audio_status().engine
