"""Smoke test for pyttsx3 run-loop lifecycle (fresh engine + global lock)."""

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
from voice.audio_status import format_audio_status, get_audio_status, reset_audio_status
from voice.pyttsx3_lifecycle import get_lifecycle_snapshot, reset_pyttsx3_lifecycle_for_tests
from voice.tts import TTSService
from voice.tts_pyttsx3 import speak_pyttsx3_direct


def _run_action(phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, (phrase, getattr(gate, "summary", gate))
    result = ActionRegistry().execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    return result.summary


def _hang_forever(*args, **kwargs):
    while True:
        time.sleep(3600)


def test_sequential_direct_speech_no_runloop_error() -> None:
    calls = {"count": 0}
    lock = threading.Lock()
    loop_active = {"value": False}

    class _Engine:
        def say(self, _text):
            return None

        def stop(self):
            loop_active["value"] = False

        def runAndWait(self):
            with lock:
                if loop_active["value"]:
                    raise RuntimeError("run loop already started")
                loop_active["value"] = True
                calls["count"] += 1
            _hang_forever()

        def getProperty(self, _name):
            return []

        def setProperty(self, *_args, **_kwargs):
            return None

    engines = [_Engine(), _Engine(), _Engine()]
    engine_iter = iter(engines)

    def _fake_nonblocking(engine, *, text, rate_raw, on_playback_start=None, create_engine_on_worker=False):
        del create_engine_on_worker
        if on_playback_start is not None:
            on_playback_start()
        from voice.pyttsx3_completion import run_and_wait_nonblocking

        with patch("voice.audio_status.playback_audible_confirmed", return_value=True):
            return run_and_wait_nonblocking(
                engine,
                text=text or "Jarvis sequential speech test phrase.",
                rate_raw=rate_raw or "185",
            )

    phrases = [
        "Jarvis direct speech test one.",
        "Jarvis direct speech test two.",
        "Jarvis direct speech test three.",
    ]
    with patch("pyttsx3.init", side_effect=lambda: next(engine_iter)), patch(
        "voice.tts_pyttsx3._run_and_wait_with_watchdog",
        side_effect=_fake_nonblocking,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_started",
        lambda: None,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_finished",
        lambda: None,
    ):
        for phrase in phrases:
            speak_pyttsx3_direct(phrase, rate_raw="185", record_user_success=False)
            snap = get_lifecycle_snapshot()
            assert snap["speech_lock_held"] is False, snap
    assert calls["count"] == 3, calls
    print("OK sequential direct speech without run loop already started")


def main() -> None:
    reset_audio_status()
    reset_pyttsx3_lifecycle_for_tests()
    try:
        import config as cfg

        cfg.TTS_SAFE_MODE = True
        cfg.VOICE_RUNTIME_STABLE = True
    except Exception:
        pass

    mock_engine = MagicMock()

    def _noop_watchdog(engine, *, text="", rate_raw="", on_playback_start=None):
        if on_playback_start is not None:
            on_playback_start()
        from voice.pyttsx3_completion import DirectPlaybackResult

        return DirectPlaybackResult(ok=True, playback_started=True, elapsed_ms=100.0)

    with patch("pyttsx3.init", return_value=mock_engine), patch(
        "voice.tts_pyttsx3._run_and_wait_with_watchdog",
        side_effect=_noop_watchdog,
    ), patch(
        "services.runtime_monitor.run_with_timeout",
        side_effect=lambda _name, _timeout, fn, *args, **kwargs: fn(*args),
    ), patch(
        "voice.audio_verified.ask_user_audible_confirmation",
        return_value=True,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_started",
        lambda: None,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_finished",
        lambda: None,
    ):
        _run_action("test direct speech", Intent.TEST_DIRECT_SPEECH)
        print("OK test direct speech")

        _run_action("force verified direct speech confirm", Intent.FORCE_VERIFIED_DIRECT_SPEECH)
        status = get_audio_status()
        assert status.selected_verified_audio_backend == "direct_pyttsx3", status
        print("OK verify direct speech backend")

        body = format_audio_status()
        assert "Runloop active:" in body, body
        assert "Engine active:" in body, body
        assert "Speech lock held:" in body, body
        print("OK show audio status fields")

        svc = TTSService(enabled=True)
        for idx in range(3):
            assert svc.speak(f"Normal speech path test number {idx + 1}.") is True
        print("OK test normal speech path x3")

        audio = ShowAudioStatusAction().execute(
            CommandRequest(raw_text="show audio status", intent=Intent.SHOW_AUDIO_STATUS)
        )
        assert audio.status == ActionStatus.SUCCESS
        final = get_audio_status()
        assert final.normal_speech_last_path in {"pyttsx3_direct", "direct_pyttsx3"}, final
        assert final.speech_lock_held is False, final
        print("OK final audio status")

    test_sequential_direct_speech_no_runloop_error()
    print("SMOKE PASS pyttsx3_runloop")


if __name__ == "__main__":
    main()
