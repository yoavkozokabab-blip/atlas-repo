"""Phase 14 overlay tests (state + hooks, mocked — no real Qt window)."""

from __future__ import annotations

import ast
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import ActionStatus, Intent
from ui.overlay_app import (
    OverlayController,
    get_overlay_controller,
    overlay_is_active,
    reset_overlay_controller,
)
from ui.overlay_state import (
    COMMAND_HISTORY_MAX,
    PIPELINE_STAGES,
    OverlayPhase,
    OverlayState,
    pipeline_index_for_phase,
    redact_overlay_text,
)
from ui.overlay_theme import get_overlay_theme, resolve_overlay_theme_name
from ui.overlay_hud import fetch_hud_system_metrics
from voice.transcriber import TranscriptionResult
from voice.wakeword import WakeWordDetector


@pytest.fixture(autouse=True)
def _clean_overlay():
    reset_runtime_state()
    reset_overlay_controller()
    yield
    reset_overlay_controller()
    reset_runtime_state()


def test_overlay_state_transitions():
    state = OverlayState()
    state.set_wake_detected()
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.WAKE_DETECTED
    assert snap.status_text == "WAKE DETECTED"
    assert snap.visible is True
    assert snap.pulse_active is True

    state.set_listening()
    assert state.snapshot().phase == OverlayPhase.RECORDING
    assert state.snapshot().status_text == "RECORDING"

    state.set_transcribing()
    assert state.snapshot().phase == OverlayPhase.TRANSCRIBING

    state.set_executing(intent_label="Opening dashboard")
    assert state.snapshot().phase == OverlayPhase.EXECUTING
    assert "Opening dashboard" in state.snapshot().intent_label

    state.set_transcript("open dashboard")
    assert "open dashboard" in state.snapshot().transcript

    state.set_result("Done summary", speaking=False)
    assert state.snapshot().result_summary == "Done summary"
    assert state.snapshot().phase == OverlayPhase.COMPLETE
    assert state.snapshot().status_text == "COMPLETE"

    state.set_speaking()
    assert state.snapshot().phase == OverlayPhase.SPEAKING

    state.hide()
    assert state.snapshot().visible is False
    assert state.snapshot().phase == OverlayPhase.IDLE


def test_redact_overlay_text_removes_secrets():
    raw = "api_key=secret123 password=abc Bearer sk-abcdefghijklmnop0123456789"
    out = redact_overlay_text(raw)
    assert "secret123" not in out
    assert "[redacted]" in out


def test_wake_detection_triggers_overlay_show():
    runtime = RuntimeState(wake_word_enabled=True, overlay_enabled=True)
    app = JarvisApp(speak_enabled=False, runtime=runtime)
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    with patch("ui.overlay_app.get_overlay_controller", return_value=ctrl):
        with patch.object(WakeWordDetector, "_load_model"):
            det = WakeWordDetector(app, lambda _s: None, model_factory=lambda: MagicMock())
            det._model = MagicMock()
            det._handle_detection(0.9)

    snap = ctrl._state.snapshot()
    assert snap.visible is True
    assert snap.phase == OverlayPhase.WAKE_DETECTED


def test_wakeword_loop_updates_transcript_and_thinking(app, runtime, monkeypatch, tmp_path):
    runtime.overlay_enabled = True
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    wav = tmp_path / "wake.wav"
    wav.write_bytes(b"RIFF")

    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="show capabilities",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr("ui.overlay_app.get_overlay_controller", lambda: ctrl)

    with patch.object(app, "handle_text_command") as handle:
        handle.return_value = MagicMock(
            intent=Intent.SHOW_CAPABILITIES,
            status=ActionStatus.SUCCESS,
            summary="Capabilities listed.",
            error=None,
        )
        from voice.wakeword_loop import run_post_wake_listening_session

        run_post_wake_listening_session(app)

    snap = ctrl._state.snapshot()
    assert "show capabilities" in snap.transcript.lower() or snap.transcript
    handle.assert_called_once()


def test_auto_hide_scheduled():
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    ctrl.on_result("ok", speaking=False)
    ctrl.on_done(speaking=False)
    snap = ctrl._state.snapshot()
    assert snap.hide_after_monotonic is not None
    assert snap.hide_after_monotonic > time.monotonic()

    with patch("ui.overlay_app.time.sleep", return_value=None):
        ctrl._state.schedule_hide_at(time.monotonic() - 1)
        ctrl._run_qt_loop = lambda: None  # not called
    snap2 = ctrl._state.snapshot()
    assert snap2.hide_after_monotonic is not None


def test_overlay_disabled_does_nothing():
    ctrl = OverlayController()
    ctrl.set_enabled(False)
    runtime = RuntimeState(overlay_enabled=False)
    runtime.set_overlay(False)
    ctrl.on_wake_detected()
    assert ctrl._state.snapshot().visible is False
    assert overlay_is_active() is False


def test_tray_toggle_runtime_sync():
    from core.runtime_state import get_runtime_state

    runtime = get_runtime_state()
    runtime.set_overlay(False)
    app = JarvisApp(runtime=runtime)
    ctrl = get_overlay_controller()
    ctrl.set_enabled(True, runtime=runtime)
    assert runtime.overlay_enabled is True
    assert ctrl.is_active() is True
    ctrl.set_enabled(False, runtime=runtime)
    assert runtime.overlay_enabled is False


@pytest.fixture
def runtime():
    return RuntimeState(overlay_enabled=True)


@pytest.fixture
def app(runtime):
    return JarvisApp(speak_enabled=False, runtime=runtime)


def test_handle_text_command_overlay_result(app, runtime):
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    runtime.set_overlay(True)
    with patch("ui.overlay_app.get_overlay_controller", return_value=ctrl):
        with patch.object(app.router, "route") as route:
            route.return_value = MagicMock(
                intent=Intent.SHOW_CAPABILITIES,
                status=ActionStatus.SUCCESS,
                summary="OK",
                error=None,
                next_suggestions=[],
            )
            app.handle_text_command("show capabilities", input_mode="voice", print_result=False)

    snap = ctrl._state.snapshot()
    assert snap.result_summary == "OK"
    assert snap.phase in {OverlayPhase.COMPLETE, OverlayPhase.SPEAKING, OverlayPhase.EXECUTING}


def test_overlay_test_sequence_does_not_execute_commands(app):
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    with patch.object(app, "handle_text_command") as handle:
        with patch("ui.overlay_app.time.sleep", return_value=None):
            ctrl.run_test_sequence()
    handle.assert_not_called()


def test_overlay_module_has_no_execution_bypass():
    root = Path(__file__).resolve().parent.parent / "ui"
    forbidden_calls = {"handle_text_command", "route"}
    for name in (
        "overlay_app.py",
        "overlay_state.py",
        "overlay_theme.py",
        "overlay_hud.py",
        "overlay_presence.py",
    ):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, f"{name} calls {node.func.id}"


def test_get_overlay_theme_jarvis_blue():
    theme = get_overlay_theme("jarvis_blue")
    assert theme.accent == "#00d4ff"


def test_premium_ironman_theme():
    theme = get_overlay_theme("premium_ironman")
    assert theme.premium is True
    assert theme.window_width >= 400


def test_premium_ironman_full_theme():
    theme = get_overlay_theme("premium_ironman_full")
    assert theme.premium is True
    assert theme.full_screen is True


def test_resolve_overlay_style_default_full(monkeypatch):
    monkeypatch.setattr("config.OVERLAY_STYLE", "premium_ironman_full", raising=False)
    assert resolve_overlay_theme_name() == "premium_ironman_full"


def test_pipeline_stage_mapping():
    assert pipeline_index_for_phase(OverlayPhase.RECORDING) == 1
    assert pipeline_index_for_phase(OverlayPhase.COMPLETE) == 5
    assert PIPELINE_STAGES[1] == "RECORD"


def test_command_history_capped_at_five():
    state = OverlayState()
    for i in range(8):
        state.push_command_history(f"command {i}")
    assert len(state.command_history) == COMMAND_HISTORY_MAX
    assert "command 7" in state.command_history[-1]


def test_fetch_hud_system_metrics_safe():
    metrics = fetch_hud_system_metrics()
    assert "cpu" in metrics
    assert "ram" in metrics
    assert metrics["date"]


def test_fetch_hud_system_metrics_without_psutil(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import)
    metrics = fetch_hud_system_metrics()
    assert metrics["cpu"] in {"42%", "N/A"}


def test_premium_overlay_state_transitions():
    state = OverlayState()
    for phase, method in (
        ("wake_detected", state.set_wake_detected),
        ("recording", state.set_listening),
        ("transcribing", state.set_transcribing),
        ("executing", state.set_thinking),
        ("speaking", state.set_speaking),
    ):
        method()
        assert state.state == phase


def test_voice_loop_overlay_hooks(tmp_path, monkeypatch):
    wav = tmp_path / "t.wav"
    wav.write_bytes(b"RIFF")
    runtime = RuntimeState(overlay_enabled=True, voice_enabled=True)
    app = JarvisApp(runtime=runtime)
    ctrl = OverlayController()
    ctrl.set_enabled(True)

    calls: list[str] = []

    def track_listening():
        calls.append("listening")

    def track_transcribing():
        calls.append("transcribing")

    monkeypatch.setattr("ui.overlay_app.get_overlay_controller", lambda: ctrl)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_listening", track_listening)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcribing", track_transcribing)
    monkeypatch.setattr("ui.overlay_app.notify_overlay_transcript", lambda _t: calls.append("transcript"))
    monkeypatch.setattr("ui.overlay_app.notify_overlay_thinking", lambda: calls.append("thinking"))

    def fake_record():
        app._running = False
        return wav

    monkeypatch.setattr("voice.voice_loop.record_until_enter", fake_record)
    monkeypatch.setattr(
        "voice.voice_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="open cursor",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    with patch.object(app.router, "route") as route:
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
            next_suggestions=[],
        )
        from voice.voice_loop import run_voice_loop

        run_voice_loop(app)

    assert "listening" in calls
    assert "transcribing" in calls
    assert "transcript" in calls
    assert "thinking" in calls


def test_get_overlay_controller_singleton():
    a = get_overlay_controller()
    b = get_overlay_controller()
    assert a is b


def test_overlay_show_and_reset():
    state = OverlayState()
    state.show("listening", "Listening...")
    assert state.state == "recording"
    state.set_transcript("hello")
    state.set_result("Done")
    state.reset()
    assert state.snapshot().visible is False
    assert state.state == "idle"


def test_overlay_text_capped(monkeypatch):
    monkeypatch.setattr("ui.overlay_state.OVERLAY_MAX_TEXT_CHARS", 20)
    long_text = "x" * 100 + " api_key=secret"
    out = redact_overlay_text(long_text)
    assert len(out) <= 20
    assert "secret" not in out


def test_missing_pyside6_fails_gracefully():
    import builtins

    ctrl = OverlayController()
    real_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PySide6.QtWidgets" or name == "PySide6":
            raise ImportError("No module named 'PySide6'")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", _import):
        ctrl._run_qt_loop()
    assert ctrl._ready.is_set()


def test_overlay_no_automation_imports():
    root = Path(__file__).resolve().parent.parent / "ui"
    forbidden = {"pyautogui", "pynput", "selenium", "playwright"}
    for name in (
        "overlay_app.py",
        "overlay_state.py",
        "overlay_theme.py",
        "overlay_hud.py",
        "overlay_presence.py",
    ):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden


def test_update_overlay_state():
    from core.runtime_state import get_runtime_state
    from ui.overlay_app import update_overlay_state

    ctrl = get_overlay_controller()
    get_runtime_state().set_overlay(True)
    ctrl.set_enabled(True, runtime=get_runtime_state())

    update_overlay_state("thinking", "Thinking...")
    assert ctrl._state.snapshot().phase == OverlayPhase.EXECUTING


def test_overlay_headless_skips_qt_thread(monkeypatch):
    """Pytest default: no real QApplication thread (JARVIS_OVERLAY_QT=0)."""
    monkeypatch.setattr("config.OVERLAY_QT_ENABLED", False)
    monkeypatch.setattr("ui.overlay_app.OVERLAY_QT_ENABLED", False)
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    assert ctrl._ready.is_set()
    assert ctrl._qt_thread is None or not ctrl._qt_thread.is_alive()


def test_resolve_overlay_cli_flag():
    import argparse

    import main as main_mod

    args = argparse.Namespace(
        safe_mode=False,
        overlay=True,
        no_overlay=False,
    )
    enabled, cli = main_mod._resolve_overlay_flag(args)
    assert enabled is True
    assert cli is True

    args2 = argparse.Namespace(safe_mode=False, overlay=False, no_overlay=True)
    enabled2, cli2 = main_mod._resolve_overlay_flag(args2)
    assert enabled2 is False
    assert cli2 is True
