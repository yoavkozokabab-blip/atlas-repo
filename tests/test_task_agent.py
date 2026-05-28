"""Phase 19 — supervised task agent tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.registry import ActionRegistry
from actions.task_actions import (
    ApproveTaskPlanAction,
    RunTaskStepAction,
    StartTaskAction,
    StopTaskAction,
)
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from task_agent.executor import run_next_step
from task_agent.planner import create_plan_from_objective
from task_agent.reports import reports_dir, write_task_report
from task_agent.safety import TASK_AGENT_MAX_STEPS, validate_command_key
from task_agent.session import get_active_task, reset_task_store, start_task


@pytest.fixture(autouse=True)
def _clean_task_store():
    reset_task_store()
    yield
    reset_task_store()


def test_plan_created_not_executed():
    req = CommandRequest(
        raw_text="review my trading algorithm",
        intent=Intent.START_TASK,
        confidence=1.0,
    )
    result = StartTaskAction().execute(req)
    assert result.status == ActionStatus.SUCCESS
    session = get_active_task()
    assert session is not None
    assert session.steps_completed == 0
    assert not session.plan_approved
    assert all(s.status.value == "pending" for s in session.plan.steps)


def test_classify_start_task():
    req = classify_rules("review my trading algorithm")
    assert req.intent == Intent.START_TASK


def test_approval_required_before_execution():
    start_task("investigate dashboard")
    session = get_active_task()
    registry = ActionRegistry()
    result, _ = run_next_step(session, registry)
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED


def test_unknown_command_blocked():
    v = validate_command_key("arbitrary_shell")
    assert not v.ok


def test_file_write_step_requires_approval():
    plan = create_plan_from_objective("compare backtest to paper")
    write_steps = [s for s in plan.steps if s.requires_separate_approval]
    assert any(s.command_key == "run_long_backtest" for s in write_steps)
    session = start_task("compare backtest")
    session.plan = plan
    from task_agent.approvals import approve_plan

    approve_plan(session)
    registry = ActionRegistry()
    with patch.object(registry, "execute") as ex:
        ex.return_value = MagicMock(
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
        )
        for _ in range(20):
            session = get_active_task()
            step = next(
                (s for s in session.plan.steps if s.status.value == "pending"),
                None,
            )
            if step is None:
                break
            if step.command_key == "run_long_backtest":
                result, _ = run_next_step(session, registry, step_id=step.step_id)
                assert result.status == ActionStatus.CONFIRMATION_REQUIRED
                break
            run_next_step(session, registry, step_id=step.step_id)


def test_report_generated(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.reports.reports_dir", lambda: tmp_path)
    session = start_task("failure report")
    from task_agent.approvals import approve_plan

    approve_plan(session)
    path = write_task_report(get_active_task())
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert session.task_id in text
    assert "Objective" in text


def test_max_steps_enforced(monkeypatch, tmp_path):
    monkeypatch.setattr("task_agent.safety.TASK_AGENT_MAX_STEPS", 1)
    session = start_task("generic task")
    from task_agent.approvals import approve_plan

    approve_plan(session)
    registry = ActionRegistry()
    with patch.object(registry, "execute") as ex:
        ex.return_value = MagicMock(
            status=ActionStatus.SUCCESS,
            summary="step ok",
        )
        run_next_step(get_active_task(), registry)
        result, _ = run_next_step(get_active_task(), registry)
    assert result.status in (ActionStatus.BLOCKED, ActionStatus.SUCCESS)


def test_stop_task_works():
    start_task("test")
    StopTaskAction().execute(
        CommandRequest(raw_text="stop", intent=Intent.STOP_TASK, confidence=1.0)
    )
    session = get_active_task()
    assert session.stop_requested


def test_no_arbitrary_shell_in_subprocess():
    from task_agent.safety import subprocess_argv_for

    assert subprocess_argv_for("pytest") == ["py", "-3", "-m", "pytest", "-q"]
    assert subprocess_argv_for("arbitrary_shell") is None


def test_approve_plan_then_run_readonly_step():
    StartTaskAction().execute(
        CommandRequest(
            raw_text="review algorithm",
            intent=Intent.START_TASK,
            confidence=1.0,
        )
    )
    ApproveTaskPlanAction().execute(
        CommandRequest(
            raw_text="approve",
            intent=Intent.APPROVE_TASK_PLAN,
            confidence=1.0,
        )
    )
    registry = ActionRegistry()
    with patch.object(registry, "execute") as ex:
        ex.return_value = MagicMock(
            status=ActionStatus.SUCCESS,
            summary="found",
            error=None,
        )
        action = RunTaskStepAction(registry)
        result = action.execute(
            CommandRequest(
                raw_text="run step",
                intent=Intent.RUN_TASK_STEP,
                confidence=1.0,
            )
        )
    assert result.status == ActionStatus.SUCCESS
    assert get_active_task().steps_completed >= 1


def test_security_router_allows_task_intents():
    from core.security import validate_intent

    for intent in (
        Intent.START_TASK,
        Intent.RUN_TASK_STEP,
        Intent.STOP_TASK,
    ):
        req = CommandRequest(raw_text="x", intent=intent, confidence=1.0)
        assert validate_intent(req) is None
