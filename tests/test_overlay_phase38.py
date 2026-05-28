"""Phase 38a — runtime presence overlay tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from ui.overlay_app import OverlayController, get_overlay_controller, reset_overlay_controller
from ui.overlay_presence import (
    intent_display_label,
    sanitize_suggestion_chips,
)
from ui.overlay_state import OverlayPhase, OverlayState
from ui.quiet_mode import init_quiet_mode_from_config, is_quiet_mode, reset_quiet_mode_state


@pytest.fixture(autouse=True)
def _clean():
    reset_runtime_state()
    reset_overlay_controller()
    reset_quiet_mode_state()
    init_quiet_mode_from_config()
    yield
    reset_overlay_controller()
    reset_runtime_state()
    reset_quiet_mode_state()


def test_overlay_phase_transitions_38a():
    state = OverlayState()
    state.set_recording()
    assert state.snapshot().phase == OverlayPhase.RECORDING
    assert "Recording" in state.snapshot().sub_status_text

    state.set_transcribing()
    assert state.snapshot().phase == OverlayPhase.TRANSCRIBING

    state.set_executing(intent_label="Reviewing trading diagnostics")
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.EXECUTING
    assert snap.intent_label == "Reviewing trading diagnostics"

    state.set_awaiting_confirmation(intent_label="Opening dashboard")
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.AWAITING_CONFIRMATION
    assert "confirmation" in snap.sub_status_text.lower()
    assert "yes" in snap.sub_status_text.lower()

    state.set_complete(summary="Done", suggestions=["show capabilities"])
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.COMPLETE
    assert len(snap.suggestions) == 1


def test_suggestion_chips_hidden_when_empty():
    state = OverlayState()
    state.set_suggestions([])
    assert state.snapshot().suggestions == ()
    chips = sanitize_suggestion_chips(["open dashboard", "run diagnostics", "", "open dashboard"])
    assert len(chips) == 2


def test_suggestion_chips_max_four_and_truncation():
    long_phrase = "open trading dashboard health check " * 3
    chips = sanitize_suggestion_chips(["one", "two", "three", long_phrase, "five"])
    assert len(chips) == 4
    assert all(len(c) <= 49 for c in chips)
    assert chips[-1].endswith("…")


def test_intent_label_redacts_secrets():
    label = intent_display_label("analyze_active_window")
    assert label == "Analyzing active window"
    chip = sanitize_suggestion_chips(["password=secret123"])[0]
    assert "secret123" not in chip


def test_confirmation_overlay_from_app():
    runtime = RuntimeState(overlay_enabled=True)
    app = JarvisApp(runtime=runtime)
    ctrl = OverlayController()
    ctrl.set_enabled(True, runtime=runtime)

    result = CommandResult(
        intent=Intent.OPEN_TRADING_DASHBOARD,
        status=ActionStatus.CONFIRMATION_REQUIRED,
        summary="Needs confirm",
        requires_confirmation=True,
    )
    with patch("ui.overlay_app.get_overlay_controller", return_value=ctrl):
        with patch("ui.overlay_app._runtime_overlay_enabled", return_value=True):
            app._notify_overlay_result(result)

    snap = ctrl._state.snapshot()
    assert snap.phase == OverlayPhase.AWAITING_CONFIRMATION
    assert "Opening dashboard" in snap.intent_label


def test_tts_speaking_sync_order(monkeypatch):
    runtime = RuntimeState(overlay_enabled=True, speak_enabled=True)
    ctrl = OverlayController()
    ctrl.set_enabled(True, runtime=runtime)
    monkeypatch.setattr("ui.overlay_app._runtime_overlay_enabled", lambda: True)

    def _result():
        ctrl._state.set_result(
            "Summary line",
            suggestions=("help",),
            intent_label="OK",
        )

    ctrl._run_update(_result)
    assert ctrl._state.snapshot().phase == OverlayPhase.COMPLETE

    ctrl._run_update(lambda: ctrl._state.set_speaking())
    assert ctrl._state.snapshot().phase == OverlayPhase.SPEAKING

    snap = ctrl._state.snapshot()
    ctrl._run_update(
        lambda: ctrl._state.set_complete(
            summary=snap.result_summary,
            show_result=False,
            suggestions=snap.suggestions,
        )
    )
    assert ctrl._state.snapshot().phase == OverlayPhase.COMPLETE


def test_ready_state_quiet_mode():
    state = OverlayState()
    state.set_ready(quiet=True)
    snap = state.snapshot()
    assert snap.phase == OverlayPhase.READY
    assert snap.quiet_ready is True
    assert snap.visible is False


def test_overlay_presence_module_no_execution():
    from pathlib import Path
    import ast

    root = Path(__file__).resolve().parent.parent / "ui" / "overlay_presence.py"
    tree = ast.parse(root.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"handle_text_command", "route", "execute"}


def test_fast_ack_uses_executing_phase(monkeypatch):
    runtime = RuntimeState(overlay_enabled=True)
    ctrl = OverlayController()
    ctrl.set_enabled(True, runtime=runtime)
    monkeypatch.setattr("ui.overlay_app.get_overlay_controller", lambda: ctrl)
    monkeypatch.setattr("ui.overlay_app._runtime_overlay_enabled", lambda: True)

    from conversation.latency_hints import deliver_fast_ack

    deliver_fast_ack("Opening...", input_mode="voice", intent="open_trading_dashboard")
    snap = ctrl._state.snapshot()
    assert snap.phase == OverlayPhase.EXECUTING
    assert snap.sub_status_text == "Opening..."


def test_workflow_hint_on_runner_step(monkeypatch):
    from workflows.runner import WorkflowRunner
    from workflows.registry import get_workflow

    hints: list[str] = []

    def _capture(h: str) -> None:
        hints.append(h)

    monkeypatch.setattr("ui.overlay_app.notify_overlay_workflow", _capture)

    wf = get_workflow("jarvis_self_check")
    if wf is None:
        pytest.skip("jarvis_self_check workflow missing")

    def _fake_execute(text: str) -> CommandResult:
        return CommandResult(
            intent=Intent.SHOW_JARVIS_STATUS,
            status=ActionStatus.SUCCESS,
            summary=f"ok {text[:20]}",
        )

    WorkflowRunner(_fake_execute).run("jarvis_self_check")
    assert hints
