"""Runtime stabilization + voice quality hardening."""

from __future__ import annotations

import json
import ast
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from actions.voice_audio_actions import (
    CalibrateVoiceAction,
    DiagnoseVoiceRuntimeAction,
    ResetJarvisRuntimeAction,
    TestVoiceOutputAction,
)
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent
from ui.overlay_app import OverlayController, get_overlay_controller, reset_overlay_controller
from ui.overlay_state import OverlayPhase, OverlayState
from voice.audio_status import get_audio_status, reset_audio_status
from voice.spoken_normalization import normalize_spoken_command
from voice.voice_calibration import run_voice_calibration
from voice.voice_debug_store import (
    get_voice_debug_snapshot,
    record_transcript_debug,
    reset_voice_debug_store,
)


@pytest.fixture(autouse=True)
def _clean_state():
    reset_overlay_controller()
    reset_audio_status()
    reset_voice_debug_store()
    yield
    reset_overlay_controller()
    reset_audio_status()
    reset_voice_debug_store()


def test_successful_command_stays_visible_long_enough(monkeypatch):
    monkeypatch.setattr("ui.overlay_app.OVERLAY_AUTO_HIDE_SECONDS", 12)
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    ctrl.on_result("OK", speaking=False)
    snap = ctrl._state.snapshot()

    assert snap.phase == OverlayPhase.COMPLETE
    assert snap.hide_after_monotonic is not None
    assert snap.hide_after_monotonic - time.monotonic() >= 10.5


def test_suggestions_extend_overlay_visibility(monkeypatch):
    monkeypatch.setattr("ui.overlay_app.OVERLAY_AUTO_HIDE_SECONDS", 12)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_READY_VISIBLE_SECONDS", 8)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_STAY_OPEN_ON_SUGGESTIONS", True)
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    ctrl.on_result("OK", speaking=False, suggestions=["show voice debug"])
    snap = ctrl._state.snapshot()

    assert snap.suggestions
    assert snap.hide_after_monotonic is not None
    assert snap.hide_after_monotonic - time.monotonic() >= 18.5


def test_errors_do_not_vanish_instantly(monkeypatch):
    monkeypatch.setattr("ui.overlay_app.OVERLAY_AUTO_HIDE_SECONDS", 12)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_READY_VISIBLE_SECONDS", 8)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_STAY_OPEN_ON_ERROR", True)
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    ctrl.on_error("No audio captured.")
    snap = ctrl._state.snapshot()

    assert snap.phase == OverlayPhase.ERROR
    assert "Try saying:" in snap.error_message
    assert snap.hide_after_monotonic is not None
    assert snap.hide_after_monotonic - time.monotonic() >= 18.5


def test_quiet_mode_still_hides_eventually(monkeypatch):
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    hidden: list[bool] = []
    monkeypatch.setattr("ui.quiet_mode.is_quiet_mode", lambda: True)
    monkeypatch.setattr("ui.quiet_mode.hide_overlay_after_auto_hide", lambda: hidden.append(True))

    ctrl._state.set_ready()
    ctrl._hide_or_quiet()

    assert ctrl._state.snapshot().quiet_ready is True
    assert hidden == [True]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("show audio state", "show audio status"),
        ("try speaking", "test voice output"),
        ("describe my screen", "describe screen"),
        ("open the trading view", "open tradingview"),
        ("open this cord", "open discord"),
        ("what did you hear", "show voice debug"),
    ],
)
def test_common_misheard_phrases_normalize(raw: str, expected: str):
    assert normalize_spoken_command(raw) == expected


@pytest.mark.parametrize(
    "phrase,intent",
    [
        ("calibrate voice", Intent.CALIBRATE_VOICE),
        ("diagnose voice runtime", Intent.DIAGNOSE_VOICE_RUNTIME),
        ("reset jarvis runtime", Intent.RESET_JARVIS_RUNTIME),
        ("can you hear me", Intent.SHOW_JARVIS_STATUS),
        ("why can't i hear you", Intent.DIAGNOSE_VOICE_RUNTIME),
        ("show what you heard", Intent.SHOW_VOICE_DEBUG),
        ("say something", Intent.TEST_VOICE_OUTPUT),
    ],
)
def test_natural_aliases_classify(phrase: str, intent: Intent):
    assert classify_rules(phrase).intent == intent


def test_voice_debug_exposes_safe_fields(monkeypatch):
    monkeypatch.setattr("config.STT_BEAM_SIZE", 3, raising=False)
    record_transcript_debug(
        raw="open dash board",
        normalized="open dashboard",
        avg_logprob=-0.3,
        low_confidence=True,
    )

    snap = get_voice_debug_snapshot()

    assert snap.last_raw_transcript == "open dash board"
    assert snap.stt_model
    assert snap.stt_backend is not None
    assert snap.stt_beam_size == 3
    assert snap.failed_transcripts


def test_calibration_stores_safe_samples_only(tmp_path, monkeypatch):
    path = tmp_path / "voice_calibration.json"
    monkeypatch.setattr("voice.voice_calibration.VOICE_CALIBRATION_PATH", path)

    result = run_voice_calibration(
        ["open dash board", "password=abc123", "show audio state"]
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert result.samples
    assert "password" not in json.dumps(payload).lower()
    assert payload["samples"][0]["normalized_transcript"] == "open dashboard"


def test_calibrate_voice_action_uses_registry_shape(tmp_path, monkeypatch):
    path = tmp_path / "voice_calibration.json"
    monkeypatch.setattr("voice.voice_calibration.VOICE_CALIBRATION_PATH", path)

    result = CalibrateVoiceAction().execute(
        CommandRequest(raw_text="calibrate voice", intent=Intent.CALIBRATE_VOICE)
    )

    assert result.status.value == "success"
    assert path.is_file()
    assert result.data["sample_count"] >= 3


def test_tts_startup_self_test_records_result(monkeypatch):
    reset_audio_status()
    monkeypatch.setattr("config.TTS_STARTUP_SELF_TEST", True, raising=False)
    monkeypatch.setattr("voice.tts_startup.TTSService", lambda enabled=True: MagicMock(speak=lambda _t: True))
    monkeypatch.setattr("voice.tts_startup.probe_output_device", lambda: "default")

    from voice.tts_startup import run_tts_startup_self_test

    run_tts_startup_self_test(enabled=True)

    assert get_audio_status().startup_self_test
    assert "ok" in get_audio_status().startup_self_test


def test_test_voice_output_attempts_speech(monkeypatch):
    calls: list[str] = []

    class FakeTTS:
        def __init__(self, *, enabled: bool):
            self.enabled = enabled

        def speak(self, text: str) -> bool:
            calls.append(text)
            return True

    monkeypatch.setattr("actions.voice_audio_actions.TTSService", FakeTTS)

    result = TestVoiceOutputAction().execute(
        CommandRequest(raw_text="test voice output", intent=Intent.TEST_VOICE_OUTPUT)
    )

    assert result.status.value == "success"
    assert calls


def test_diagnose_reports_degraded_states(monkeypatch):
    monkeypatch.setattr(
        "voice.microphone.check_microphone_available",
        lambda: (_ for _ in ()).throw(RuntimeError("no mic")),
    )

    result = DiagnoseVoiceRuntimeAction().execute(
        CommandRequest(raw_text="diagnose voice runtime", intent=Intent.DIAGNOSE_VOICE_RUNTIME)
    )

    assert result.status.value == "success"
    assert "degraded" in result.summary
    assert "recommended_safe_steps" in result.summary


def test_reset_clears_stuck_overlay_without_destructive_cleanup():
    ctrl = get_overlay_controller()
    ctrl.set_enabled(True)
    ctrl._state.set_recording()
    record_transcript_debug(raw="bad", normalized="", low_confidence=True)

    result = ResetJarvisRuntimeAction().execute(
        CommandRequest(raw_text="reset jarvis runtime", intent=Intent.RESET_JARVIS_RUNTIME)
    )

    assert result.status.value == "success"
    assert ctrl._state.snapshot().phase == OverlayPhase.IDLE
    assert result.data["destructive_cleanup"] is False


def test_voice_runtime_actions_do_not_use_shell():
    source = Path("actions/voice_audio_actions.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_names = {"subprocess", "os.system", "popen", "powershell"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.lower() not in forbidden_names
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.lower() not in forbidden_names
        if isinstance(node, ast.Call):
            text = ast.unparse(node.func).lower()
            assert text not in forbidden_names


def test_hud_snapshot_includes_transcript_result_suggestions_and_redaction():
    state = OverlayState()
    state.set_ready()
    state.set_transcript("open dashboard api_key=secret123")
    state.set_result("Dashboard opened", suggestions=["show voice debug"])
    snap = state.snapshot()

    assert "I heard:" in snap.transcript
    assert "secret123" not in snap.transcript
    assert snap.result_summary == "Dashboard opened"
    assert snap.suggestions
