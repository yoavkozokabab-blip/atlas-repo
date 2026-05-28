"""TTS failure visibility — async status, fast-ack logging, edge playback errors."""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from conversation.latency_hints import deliver_fast_ack
from voice.tts import TTSError, TTSService
from voice.tts_edge import EdgeTTSError, _play_mp3
from voice.tts_status import (
    format_tts_status,
    get_tts_status,
    record_tts_async_failure,
    reset_tts_status_cache,
)


@pytest.fixture(autouse=True)
def _reset_tts():
    reset_tts_status_cache()
    svc = TTSService(enabled=True)
    svc.reset_engine()
    from voice.tts_pyttsx3 import reset_pyttsx3_engine

    reset_pyttsx3_engine()
    yield
    reset_tts_status_cache()


def test_async_tts_failure_recorded(monkeypatch, capsys):
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "edge_tts", raising=False)
    svc = TTSService(enabled=True)
    workers: list[threading.Thread] = []
    real_start = threading.Thread.start

    def _track_start(self, *args, **kwargs):
        workers.append(self)
        return real_start(self, *args, **kwargs)

    def _fail(_safe: str) -> bool:
        raise TTSError("edge down; pyttsx3: also down")

    with (
        patch.object(threading.Thread, "start", _track_start),
        patch.object(svc, "_speak_blocking", side_effect=_fail),
    ):
        assert svc.speak("hello") is True
        for worker in workers:
            if not (worker.name or "").startswith("jarvis-tts"):
                continue
            worker.join(timeout=5.0)
            assert not worker.is_alive()

    status = get_tts_status()
    assert status.async_failure_count == 1
    assert status.last_success is False
    assert status.last_error is not None
    assert "edge down" in status.last_error
    out = capsys.readouterr().out
    assert "[WARNING] TTS:" in out


def test_fast_ack_tts_failure_logged(monkeypatch, caplog):
    monkeypatch.setattr("conversation.latency_hints.CONVERSATION_FAST_ACK_ENABLED", True)
    caplog.set_level(logging.WARNING, logger="jarvis.conversation.latency")

    class _FakeRuntime:
        speak_enabled = True

    with (
        patch("core.runtime_state.get_runtime_state", return_value=_FakeRuntime()),
        patch(
            "voice.tts.TTSService.speak",
            side_effect=RuntimeError("tts boom"),
        ),
        patch("ui.overlay_app.notify_overlay_fast_ack"),
    ):
        deliver_fast_ack("Got it — checking...", input_mode="voice", speak=True)

    assert any("Fast-ack TTS failed" in r.message for r in caplog.records)


def test_edge_playback_failure_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"\x00" * 64)

    with (
        patch("voice.tts_edge._play_mp3_playsound", side_effect=ImportError("no playsound")),
        patch(
            "voice.tts_edge._play_mp3_powershell_wmp",
            side_effect=EdgeTTSError(
                "Windows MP3 playback (PowerShell/WMP) failed rc=1 stderr/stdout=WMP broken"
            ),
        ),
        patch("voice.tts_edge._play_mp3_mci", side_effect=OSError("MCI unavailable")),
    ):
        with pytest.raises(EdgeTTSError) as exc_info:
            _play_mp3(mp3)

    msg = str(exc_info.value)
    assert "MP3 playback failed" in msg
    assert "powershell/WMP" in msg.lower() or "PowerShell" in msg


def test_show_tts_status_includes_last_error():
    record_tts_async_failure("playback timeout", provider="edge_tts")
    text = format_tts_status()
    assert "Last engine: edge_tts" in text
    assert "Last success: no" in text
    assert "Last error: playback timeout" in text
    assert "Async failure count: 1" in text


def test_blocking_tts_success_no_async_failure_count(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("config.TTS_ENGINE", "pyttsx3", raising=False)
    svc = TTSService(enabled=True)

    with patch.object(svc, "_speak_pyttsx3"):
        assert svc.speak("Done.") is True

    status = get_tts_status()
    assert status.last_provider == "pyttsx3"
    assert status.last_success is True
    assert status.last_error is None
    assert status.async_failure_count == 0
