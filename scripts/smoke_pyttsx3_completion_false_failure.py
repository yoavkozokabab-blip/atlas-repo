"""Smoke: pyttsx3 completion must not false-fail after runAndWait end."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from actions.voice_audio_actions import ShowAudioStatusAction, TestNormalSpeechPathAction
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from voice.audio_status import format_audio_status, get_audio_status, reset_audio_status
from voice.pyttsx3_lifecycle import reset_pyttsx3_lifecycle_for_tests
from voice.tts_pyttsx3 import speak_pyttsx3_direct


def _run_action(phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, gate
    result = ActionRegistry().execute(req)
    assert result.status == ActionStatus.SUCCESS, result.summary
    return result.summary


def test_grace_window_delayed_completion() -> None:
    """Estimated timeout fires, then runAndWait returns within grace window."""
    from voice.pyttsx3_completion import run_and_wait_nonblocking

    class _Engine:
        def runAndWait(self):
            time.sleep(3.5)

    with patch("voice.audio_status.playback_audible_confirmed", return_value=False):
        result = run_and_wait_nonblocking(
            _Engine(),
            text="Short phrase.",
            rate_raw="185",
            on_playback_start=lambda: None,
        )
    assert result.ok is True, result
    assert result.delayed_completion_recovered is True, result
    status = get_audio_status()
    assert status.delayed_completion_recovered is True, status
    print("OK grace window delayed completion recovered")


def test_late_runandwait_return_is_success() -> None:
    class _Engine:
        def say(self, _text):
            return None

        def stop(self):
            return None

        def runAndWait(self):
            time.sleep(0.85)

        def getProperty(self, _name):
            return []

        def setProperty(self, *_args, **_kwargs):
            return None

    with patch("pyttsx3.init", return_value=_Engine()), patch(
        "voice.audio_status.playback_audible_confirmed",
        return_value=False,
    ):
        speak_pyttsx3_direct(
            "Short phrase.",
            rate_raw="185",
            record_user_success=False,
        )
    print("OK late runAndWait return counts as success")


def main() -> None:
    reset_audio_status()
    reset_pyttsx3_lifecycle_for_tests()
    try:
        import config as cfg

        cfg.TTS_SAFE_MODE = True
        cfg.VOICE_RUNTIME_STABLE = True
        cfg.FORCE_AUDIO_SUCCESS_FOR_DEBUG = True
    except Exception:
        pass

    from voice.audio_runtime_init import initialize_audio_runtime_at_startup

    initialize_audio_runtime_at_startup()

    test_grace_window_delayed_completion()
    test_late_runandwait_return_is_success()

    with patch(
        "services.runtime_monitor.run_with_timeout",
        side_effect=lambda _name, _timeout, fn, *args, **kwargs: fn(*args),
    ), patch(
        "ui.overlay_app.notify_overlay_tts_started",
        lambda: None,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_finished",
        lambda: None,
    ):
        _run_action("test direct speech", Intent.TEST_DIRECT_SPEECH)
        print("OK test direct speech")

        status = get_audio_status()
        assert status.selected_verified_audio_backend == "direct_pyttsx3", status
        assert status.playback_audible_confirmed is True, status
        assert status.speech_success_heuristic_active is True, status
        print("OK show audio status pre-check")

        for idx in range(3):
            normal = TestNormalSpeechPathAction().execute(
                CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
            )
            assert normal.status == ActionStatus.SUCCESS, (idx, normal.summary)
        print("OK test normal speech path x3")

        body = format_audio_status()
        assert "Verified backend: direct_pyttsx3" in body, body
        assert "Playback audible confirmed: yes" in body, body
        assert "Speech success heuristic active: yes" in body, body
        assert "Delayed completion recovered:" in body, body
        assert "Completion grace active:" in body, body
        assert "Worker grace elapsed ms:" in body, body
        assert "Completion pipeline version: v2" in body, body
        assert "Grace recovery enabled: yes" in body, body
        assert "Legacy path detected: no" in body, body
        assert "Debug force enabled: yes" in body, body
        ShowAudioStatusAction().execute(
            CommandRequest(raw_text="show audio status", intent=Intent.SHOW_AUDIO_STATUS)
        )
        print("OK show audio status")

    print("SMOKE PASS pyttsx3_completion_false_failure")


if __name__ == "__main__":
    main()
