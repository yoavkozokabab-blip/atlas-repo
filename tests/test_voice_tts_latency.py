"""TTS attempt + latency recording for wake/voice commands."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from config import STT_LOW_CONFIDENCE_BLOCK_WAKE
from core.app import JarvisApp
from core.results import result_success
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import ActionStatus, Intent
from voice.latency_tracker import (
    begin_voice_command,
    finish_and_log,
    get_last_latency,
    mark_tts_pending,
    reset_latency_tracker,
    set_tts_ms,
)
from voice.stt_empty_guidance import empty_wake_overlay_message, notify_empty_wake_transcript
from voice.stt_diagnostics import record_empty_wake_guidance, reset_stt_diagnostics, snapshot
from voice.stt_profile import apply_voice_profile
from voice.transcriber import TranscriptionResult


@pytest.fixture(autouse=True)
def _reset():
    reset_latency_tracker()
    reset_runtime_state()
    reset_stt_diagnostics()
    yield
    reset_latency_tracker()
    reset_stt_diagnostics()


def test_wake_command_attempts_tts(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", False, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", False, raising=False)
    app = JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))
    spoken: list[str] = []

    with patch.object(app.tts, "speak", side_effect=lambda t: spoken.append(t) or True):
        begin_voice_command(source="wakeword")
        app.handle_text_command(
            "open dashboard",
            input_mode="wakeword",
            print_result=False,
        )
        finish_and_log()

    assert spoken
    rec = get_last_latency()
    assert rec is not None
    assert rec.tts_ms is not None
    assert rec.tts_ms > 0


def test_async_tts_ms_recorded_after_wait(monkeypatch):
    monkeypatch.setattr("config.TTS_ASYNC", True, raising=False)
    monkeypatch.setattr("voice.tts.TTS_ASYNC", True, raising=False)
    app = JarvisApp(speak_enabled=True, runtime=RuntimeState(speak_enabled=True))
    done = threading.Event()

    def _speak(text: str) -> bool:
        mark_tts_pending()

        def _finish() -> None:
            time.sleep(0.05)
            set_tts_ms(42.0)
            done.set()

        threading.Thread(target=_finish, daemon=True).start()
        return True

    with patch.object(app.tts, "speak", side_effect=_speak):
        begin_voice_command(source="wakeword")
        app.handle_text_command(
            "open dashboard",
            input_mode="wakeword",
            print_result=False,
        )
        finish_and_log(wait_for_tts=True, tts_wait_seconds=2.0)

    assert done.wait(timeout=1.0)
    rec = get_last_latency()
    assert rec is not None
    assert rec.tts_ms == 42.0


def test_fast_profile_disables_low_confidence_block():
    out = apply_voice_profile(
        voice_profile="fast",
        stt_fast_profile=True,
        fast_voice_mode=True,
        model_raw="medium",
        beam_size=3,
        wake_max_listen_seconds=5.0,
        low_confidence_block_wake_env=True,
    )
    assert out.low_confidence_block_wake is False


def test_fast_profile_env_disables_low_confidence_block(monkeypatch):
    import importlib

    monkeypatch.setenv("VOICE_PROFILE", "fast")
    monkeypatch.setenv("STT_LOW_CONFIDENCE_BLOCK_WAKE", "true")
    monkeypatch.setenv("STT_MODEL", "medium")
    import config as cfg

    importlib.reload(cfg)
    assert cfg.VOICE_PROFILE == "fast"
    assert cfg.STT_LOW_CONFIDENCE_BLOCK_WAKE is False
    assert cfg.STT_MODEL == "small"


def test_repeated_empty_transcript_guidance():
    msg1 = notify_empty_wake_transcript()
    msg2 = empty_wake_overlay_message()
    assert "wake word" in msg1.lower()
    record_empty_wake_guidance()
    msg3 = empty_wake_overlay_message()
    assert "open dashboard" in msg3.lower()
    snap = snapshot()
    assert snap.consecutive_empty_wake >= 2


def test_maybe_speak_skips_when_disabled():
    app = JarvisApp(speak_enabled=False, runtime=RuntimeState(speak_enabled=False))
    begin_voice_command()
    with patch.object(app.tts, "speak") as speak:
        app._maybe_speak_result(
            result_success(Intent.OPEN_CHROME, "Opened Chrome.")
        )
    speak.assert_not_called()
    finish_and_log()
    rec = get_last_latency()
    assert rec is not None
    assert rec.tts_note.startswith("skipped:")
