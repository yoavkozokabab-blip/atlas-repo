"""Workflow runner tests."""

from unittest.mock import MagicMock, patch

import pytest

from actions.workflow_actions import ListWorkflowsAction, RunWorkflowAction
from brain.intent_classifier import classify_rules
from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS
from core.app import JarvisApp
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from workflows.models import WorkflowDefinition, WorkflowStep
from workflows.registry import get_workflow, reset_workflow_registry
from workflows.runner import WorkflowRunner


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_workflow_registry()
    yield
    reset_workflow_registry()


def _ok(intent: str, summary: str = "ok") -> CommandResult:
    return CommandResult(
        intent=Intent(intent),
        status=ActionStatus.SUCCESS,
        summary=summary,
    )


def _fail(intent: str) -> CommandResult:
    return CommandResult(
        intent=Intent(intent),
        status=ActionStatus.FAILED,
        summary="failed",
        error="failed",
    )


def _confirm(intent: str) -> CommandResult:
    return CommandResult(
        intent=Intent(intent),
        status=ActionStatus.CONFIRMATION_REQUIRED,
        summary="confirm required",
        requires_confirmation=True,
        confirmation_id="cid-1",
    )


def test_workflow_intents_allowlisted():
    names = {"list_workflows", "run_workflow", "explain_workflow"}
    assert names <= IMPLEMENTED_INTENTS
    for n in names:
        assert n not in CONFIRMATION_REQUIRED_INTENTS


def test_hebrew_run_trading_health():
    req = classify_rules("תריץ בדיקת מערכת מסחר")
    assert req.intent == Intent.RUN_WORKFLOW
    assert req.params.get("workflow") == "trading_health_check"


def test_list_workflows():
    result = ListWorkflowsAction().execute(
        CommandRequest(raw_text="list workflows", intent=Intent.LIST_WORKFLOWS)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "trading_health_check" in result.summary


def test_unknown_workflow_rejected():
    calls: list[str] = []

    def execute(text: str) -> CommandResult:
        calls.append(text)
        return _ok("unknown")

    runner = WorkflowRunner(execute)
    result = runner.run("nonexistent_workflow")
    assert result.status == "unknown_workflow"
    assert calls == []


def test_read_only_workflow_completes_via_router_path():
    calls: list[str] = []

    def execute(text: str) -> CommandResult:
        calls.append(text)
        return _ok("show_dashboard_health")

    runner = WorkflowRunner(execute)
    result = runner.run("trading_health_check")
    assert result.status in ("completed", "completed_with_failures")
    assert len(calls) == 4
    assert calls[0] == "show dashboard health"
    assert result.to_dict()["workflow_name"] == "trading_health_check"


def test_failed_step_does_not_crash_workflow():
    intents = [
        "show_dashboard_health",
        "show_last_errors",
        "show_rejection_reasons",
        "run_diagnostics",
    ]
    idx = {"n": 0}

    def execute(text: str) -> CommandResult:
        intent = intents[idx["n"]]
        idx["n"] += 1
        if idx["n"] == 2:
            return _fail(intent)
        return _ok(intent)

    result = WorkflowRunner(execute).run("trading_health_check")
    assert result.status == "completed_with_failures"
    assert 1 in result.failed_steps
    assert len(result.step_results) == 4


def test_confirm_required_step_pauses():
    def execute(text: str) -> CommandResult:
        if "daily loop" in text:
            return _confirm("run_live_daily_loop")
        return _ok("show_dashboard_health")

    wf = WorkflowDefinition(
        name="_test_confirm",
        title="Test",
        description="test",
        steps=[
            WorkflowStep("show_dashboard_health", "show dashboard health"),
            WorkflowStep("run_live_daily_loop", "run live daily loop"),
        ],
    )
    with patch("workflows.runner.get_workflow", return_value=wf):
        result = WorkflowRunner(execute).run("_test_confirm")

    assert result.status == "paused_confirmation"
    assert result.paused_at_step == 1
    assert result.confirmation_id == "cid-1"
    assert len(result.step_results) == 2


def test_run_workflow_action_uses_router_not_registry_execute():
    router = MagicMock()
    router.route.side_effect = [
        _ok("show_dashboard_health"),
        _ok("show_last_errors"),
        _ok("show_rejection_reasons"),
        _ok("run_diagnostics"),
    ]
    action = RunWorkflowAction(router=router)
    result = action.execute(
        CommandRequest(
            raw_text="run workflow trading_health_check",
            intent=Intent.RUN_WORKFLOW,
            params={"workflow": "trading_health_check"},
        )
    )
    assert router.route.call_count == 4
    assert result.data["workflow_name"] == "trading_health_check"
    assert "workflow_name" in result.data


def test_handle_text_command_path():
    app = JarvisApp()
    calls: list[str] = []

    def fake_handle(text: str, **kwargs) -> CommandResult:
        calls.append(text)
        return _ok("show_dashboard_health")

    with patch.object(app, "handle_text_command", side_effect=fake_handle):
        from workflows.runner import run_workflow_via_app

        run_workflow_via_app("jarvis_self_check", app)

    assert len(calls) == 4
    assert calls[0] == "system status"


def test_no_registry_bypass_in_workflow_package():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for rel in ("workflows/runner.py", "actions/workflow_actions.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "registry.execute" not in text
        assert "ActionRegistry" not in text or "CommandRouter" in text
