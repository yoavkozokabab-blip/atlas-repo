"""Smoke: debug audio startup wiring + normal speech not blocked in stable mode."""

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
from voice.audio_runtime_init import initialize_audio_runtime_at_startup
from voice.audio_status import format_audio_status, get_audio_status, reset_audio_status
from voice.pyttsx3_lifecycle import reset_pyttsx3_lifecycle_for_tests


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

    initialize_audio_runtime_at_startup()

    status = get_audio_status()
    assert status.completion_pipeline_version == "v2", status
    assert status.grace_recovery_enabled is True, status
    assert status.debug_force_enabled is True, status
    assert status.legacy_completion_path_detected is False, status
    assert status.selected_verified_audio_backend == "direct_pyttsx3", status
    assert status.playback_audible_confirmed is True, status

    body = format_audio_status()
    assert "Completion pipeline version: v2" in body, body
    assert "Grace recovery enabled: yes" in body, body
    assert "Debug force enabled: yes" in body, body
    assert "Verified backend: direct_pyttsx3" in body, body
    assert "Legacy path detected: no" in body, body
    print("OK show audio status fields")

    ShowAudioStatusAction().execute(
        CommandRequest(raw_text="show audio status", intent=Intent.SHOW_AUDIO_STATUS)
    )

    def _run_direct(_name, _timeout, fn, *args, **kwargs):
        kwargs.pop("detail", None)
        return fn(*args, **kwargs)

    with patch(
        "services.runtime_monitor.run_with_timeout",
        side_effect=_run_direct,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_started",
        lambda: None,
    ), patch(
        "ui.overlay_app.notify_overlay_tts_finished",
        lambda: None,
    ):
        t0 = time.perf_counter()
        normal = TestNormalSpeechPathAction().execute(
            CommandRequest(raw_text="test normal speech path", intent=Intent.TEST_NORMAL_SPEECH)
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert normal.status == ActionStatus.SUCCESS, (elapsed_ms, normal.summary)
        assert elapsed_ms >= 200.0, (elapsed_ms, normal.summary)
        assert "Normal speech path returned false" not in normal.summary, normal.summary
        print(f"OK test normal speech path ({elapsed_ms:.0f} ms)")

    print("SMOKE PASS audio_debug_startup")


if __name__ == "__main__":
    main()
