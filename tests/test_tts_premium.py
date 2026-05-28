"""Phase 18 — edge-tts premium TTS with pyttsx3 fallback."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.intent_classifier import classify_rules
from config import TTS_MAX_CHARS
from core.app import JarvisApp
from core.types import ActionStatus, CommandResult, Intent
from voice.tts import TTSError, TTSService, sanitize_for_speech
from voice.tts_config import resolve_edge_tts_rate, resolve_pyttsx_rate
from voice.tts_status import get_tts_status, reset_tts_status_cache


@pytest.fixture(autouse=True)
def _reset_tts():
    reset_tts_status_cache()
    svc = TTSService(enabled=True)
    svc.reset_engine()
    from voice.tts_pyttsx3 import reset_pyttsx3_engine

    reset_pyttsx3_engine()
    yield
    reset_tts_status_cache()


def test_rate_parsing():
    assert resolve_edge_tts_rate("+15%") == "+15%"
    assert resolve_pyttsx_rate("+15%") == 212
    assert resolve_pyttsx_rate("210") == 210


def test_edge_tts_speak_mocked(monkeypatch):
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_VOICE", "en-US-GuyNeural", raising=False)
    monkeypatch.setattr("config.TTS_RATE_RAW", "+15%", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("config.TTS_STREAMING_ENABLED", False, raising=False)

    played: list[str] = []

    with (
        patch(
            "voice.tts_edge.speak_edge_tts",
            side_effect=lambda *a, **k: played.append("spoken"),
        ),
    ):
        svc = TTSService(enabled=True)
        assert svc.speak("Hello from JARVIS.") is True

    assert played == ["spoken"]
    assert get_tts_status().last_provider == "edge_tts"


def test_speak_edge_tts_uses_edge_module(monkeypatch, tmp_path):
    pytest.importorskip("edge_tts")
    async def fake_save(path):
        Path(path).write_bytes(b"\x00" * 64)

    mock_comm = MagicMock()
    mock_comm.save = AsyncMock(side_effect=fake_save)
    played: list[str] = []

    with (
        patch("edge_tts.Communicate", return_value=mock_comm) as comm_cls,
        patch("voice.tts_edge._play_mp3", side_effect=lambda p: played.append(str(p))),
    ):
        from voice.tts_edge import speak_edge_tts

        speak_edge_tts("Hi", voice="en-US-GuyNeural", rate_raw="+15%")
        comm_cls.assert_called_once()

    assert len(played) == 1


def test_edge_failure_falls_back_to_pyttsx3(monkeypatch):
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("config.TTS_STREAMING_ENABLED", False, raising=False)
    svc = TTSService(enabled=True)

    with (
        patch.object(svc, "_speak_edge", side_effect=RuntimeError("edge down")),
        patch.object(svc, "_speak_pyttsx3") as pyttsx,
    ):
        assert svc.speak("Summary text.") is True

    pyttsx.assert_called_once()
    assert get_tts_status().last_provider == "pyttsx3_fallback"


def test_pyttsx3_only_engine(monkeypatch):
    monkeypatch.setattr("config.TTS_ENGINE", "pyttsx3", raising=False)
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    svc = TTSService(enabled=True)
    with patch.object(svc, "_speak_pyttsx3") as pyttsx:
        assert svc.speak("Done.") is True
    pyttsx.assert_called_once()


def test_async_does_not_block(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "pyttsx3", raising=False)
    svc = TTSService(enabled=True)
    gate = threading.Event()

    def slow(_safe: str) -> None:
        gate.wait(timeout=2.0)

    with patch.object(svc, "_speak_blocking", side_effect=slow):
        t0 = time.perf_counter()
        assert svc.speak("hello") is True
        assert time.perf_counter() - t0 < 0.5
    gate.set()


def test_secrets_redacted_before_tts():
    text = "Done. API_KEY=supersecret123 password=abc"
    safe = sanitize_for_speech(text)
    assert "supersecret123" not in safe
    assert "password=abc" not in safe.lower() or "[redacted]" in safe


def test_show_tts_status_action(monkeypatch):
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("voice.tts_status.TTS_ENGINE", "edge_tts", raising=False)
    monkeypatch.setattr("config.TTS_VOICE", "en-US-GuyNeural", raising=False)
    monkeypatch.setattr("config.TTS_RATE_RAW", "+15%", raising=False)
    from actions.tts_actions import ShowTtsStatusAction
    from core.types import CommandRequest

    result = ShowTtsStatusAction().execute(
        CommandRequest(
            raw_text="show tts status",
            intent=Intent.SHOW_TTS_STATUS,
            confidence=1.0,
        )
    )
    assert "edge_tts" in result.summary
    assert "en-US-GuyNeural" in result.summary
    assert "+15%" in result.summary


def test_classify_show_tts_status():
    req = classify_rules("show tts status")
    assert req.intent == Intent.SHOW_TTS_STATUS


def test_long_summary_truncated():
    long = "x" * (TTS_MAX_CHARS + 100)
    safe = sanitize_for_speech(long)
    assert len(safe) <= TTS_MAX_CHARS
    assert safe.endswith("...")
