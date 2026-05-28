"""Smoke test for non-blocking pyttsx3 COM completion recovery."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from actions.voice_audio_actions import ShowAudioStatusAction, TestNormalSpeechPathAction
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from services.runtime_monitor import get_runtime_monitor, reset_runtime_monitor
from voice.audio_status import (
    format_audio_status,
    get_audio_status,
    reset_audio_status,
    set_selected_verified_audio_backend,
)
from voice.pyttsx3_completion import DirectPlaybackResult, run_and_wait_nonblocking
from voice.tts import TTSService
from voice.tts_watchdog import end_speak_session, is_speak_active


def _run_action(phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, (phrase, getattr(gate, "summary", gate))
    result = ActionRegistry().execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    assert "not implemented" not in result.summary.lower(), result.summary
    return result.summary


def _hang_forever(*args, **kwargs):
    while True:
        time.sleep(3600)


def test_nonblocking_heuristic() -> None:
    engine = MagicMock()
    engine.runAndWait = MagicMock(side_effect=_hang_forever)
    with patch("voice.audio_status.playback_audible_confirmed", return_value=True):
        result = run_and_wait_nonblocking(
            engine,
            text="Hello from JARVIS completion recovery smoke test.",
            rate_raw="185",
        )
    assert result.ok is True, result
    assert result.completion_hang is True, result
    assert result.playback_started is True, result
    assert result.elapsed_ms >= 300.0, result
    status = get_audio_status()
    assert status.completion_hang_detected is True, status
    assert status.com_recovery_mode_active is True, status
    assert status.speech_success_heuristic_active is True, status
    print("OK nonblocking completion hang heuristic")


def test_sequential_speech_paths() -> None:
    mock_engine = MagicMock()
    mock_engine.runAndWait = MagicMock(side_effect=_hang_forever)

    def _fake_nonblocking(engine, *, text, rate_raw, on_playback_start=None, create_engine_on_worker=False):
        del create_engine_on_worker
        if on_playback_start is not None:
            on_playback_start()
        return DirectPlaybackResult(
            ok=True,
            completion_hang=True,
            playback_started=True,
            elapsed_ms=900.0,
            estimated_ms=1200.0,
        )

    svc = TTSService(enabled=True)
    phrases = [
        "First sequential phrase for completion recovery.",
        "Second sequential phrase for completion recovery.",
        "Third sequential phrase for completion recovery.",
    ]
    with patch("pyttsx3.init", return_value=mock_engine), patch(
        "voice.tts_pyttsx3._run_and_wait_with_watchdog",
        side_effect=_fake_nonblocking,
    ), patch(
        "voice.audio_verified.block_unverified_speech_with_warning",
        return_value=True,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_started",
        lambda: None,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_finished",
        lambda: None,
    ):
        for phrase in phrases:
            assert svc.speak(phrase) is True, phrase
            assert is_speak_active() is False, phrase
    print("OK three sequential phrases")


def main() -> None:
    reset_audio_status()
    reset_runtime_monitor()
    end_speak_session()
    try:
        import config as cfg

        cfg.TTS_SAFE_MODE = True
        cfg.VOICE_RUNTIME_STABLE = True
        cfg.TTS_ASYNC = False
    except Exception:
        pass

    set_selected_verified_audio_backend("direct_pyttsx3")

    timeout_names: list[str] = []
    monitor = get_runtime_monitor()

    def _track_timeout(name: str, **kwargs: object) -> None:
        timeout_names.append(name)
        monitor.record_timeout(name, **kwargs)  # type: ignore[arg-type]

    common_patches = dict(
        voice_audio_verified_patch=patch(
            "voice.audio_verified.ask_user_audible_confirmation",
            return_value=True,
        ),
        overlay_start=patch("ui.overlay_app.notify_overlay_tts_started", lambda: None),
        overlay_finish=patch("ui.overlay_app.notify_overlay_tts_finished", lambda: None),
        watchdog=patch.object(monitor, "record_timeout", side_effect=_track_timeout),
    )

    with patch(
        "voice.tts_pyttsx3._run_and_wait_with_watchdog",
        side_effect=lambda engine, *, text, rate_raw, on_playback_start=None, create_engine_on_worker=False: run_and_wait_nonblocking(
            engine,
            text=text,
            rate_raw=rate_raw,
            on_playback_start=on_playback_start,
            create_engine_on_worker=create_engine_on_worker,
        ),
    ), common_patches["voice_audio_verified_patch"], common_patches["overlay_start"], common_patches[
        "overlay_finish"
    ], common_patches["watchdog"]:
        _run_action("test direct speech", Intent.TEST_DIRECT_SPEECH)
        print("OK test direct speech")

        _run_action("force verified direct speech confirm", Intent.FORCE_VERIFIED_DIRECT_SPEECH)
        status = get_audio_status()
        assert status.playback_audible_confirmed is True, status
        assert status.selected_verified_audio_backend == "direct_pyttsx3", status
        print("OK force verified direct speech confirm")

        test_nonblocking_heuristic()

        normal = TestNormalSpeechPathAction().execute(
            CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
        )
        assert normal.status == ActionStatus.SUCCESS, normal.summary
        print("OK test normal speech path")

        test_sequential_speech_paths()

        audio = ShowAudioStatusAction().execute(
            CommandRequest(raw_text="show audio status", intent=Intent.SHOW_AUDIO_STATUS)
        )
        assert audio.status == ActionStatus.SUCCESS
        body = format_audio_status()
        assert "Playback audible confirmed: yes" in body, body
        assert "Completion hang detected: yes" in body, body
        assert "COM recovery mode active: yes" in body, body
        assert "Speech success heuristic active: yes" in body, body
        print("OK show audio status")

    assert "tts.speak" not in timeout_names, timeout_names
    print("OK no runtime degradation from tts.speak timeout")

    print("SMOKE PASS pyttsx3_completion")


if __name__ == "__main__":
    main()
