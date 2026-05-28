"""Smoke test for direct pyttsx3 verified backend wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.registry import ActionRegistry
from actions.voice_audio_actions import ShowAudioStatusAction, TestNormalSpeechPathAction
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from voice.audio_status import format_audio_status, get_audio_status, record_normal_speech_path, reset_audio_status


def _run_action(phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, (phrase, getattr(gate, "summary", gate))
    result = ActionRegistry().execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    assert "not implemented" not in result.summary.lower(), result.summary
    return result.summary


def main() -> None:
    reset_audio_status()
    try:
        import config as cfg

        cfg.TTS_SAFE_MODE = True
        cfg.VOICE_RUNTIME_STABLE = True
    except Exception:
        pass

    mock_engine = MagicMock()

    def _noop_watchdog(engine, *, text="", rate_raw="", on_playback_start=None, create_engine_on_worker=False):
        del create_engine_on_worker
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
        assert status.active_backend == "direct_pyttsx3", status
        print("OK force verified direct speech confirm")

        record_normal_speech_path("pyttsx3_direct")
        for idx in range(3):
            normal = TestNormalSpeechPathAction().execute(
                CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
            )
            assert normal.status == ActionStatus.SUCCESS, (idx, normal.summary)
        print("OK test normal speech path x3")

        audio = ShowAudioStatusAction().execute(
            CommandRequest(raw_text="show audio status", intent=Intent.SHOW_AUDIO_STATUS)
        )
        assert audio.status == ActionStatus.SUCCESS
        body = format_audio_status()
        assert "Verified backend: direct_pyttsx3" in body, body
        assert "Active backend: direct_pyttsx3" in body, body
        assert "Stable normal path equals direct: yes" in body, body
        assert "Runloop active:" in body, body
        assert "Engine active:" in body, body
        assert "Speech lock held:" in body, body
        print("OK show audio status")

    print("SMOKE PASS audio_direct_backend")


if __name__ == "__main__":
    main()
