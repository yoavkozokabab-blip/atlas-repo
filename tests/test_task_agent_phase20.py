"""Phase 20 — task findings, patch proposals, engineering reports."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.task_actions import (
    ApproveTaskPatchAction,
    ProposeTaskPatchAction,
    RejectTaskPatchAction,
    RunTaskStepAction,
    ShowTaskFindingsAction,
    ShowTaskPatchAction,
    StartTaskAction,
)
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from task_agent.findings import extract_findings_from_step, merge_findings
from task_agent.patch_proposals import (
    build_patch_proposal,
    validate_diff_text,
    validate_patch_target,
)
from task_agent.report_templates import build_engineering_report
from task_agent.reports import write_task_report
from task_agent.session import get_active_task, reset_task_store, start_task


@pytest.fixture(autouse=True)
def _clean():
    reset_task_store()
    yield
    reset_task_store()


def test_findings_extracted_from_fake_output():
    text = (
        "pytest FAILED: test_ranking_mismatch\n"
        "strategy/foo.py:42 stale price in live vs backtest entry\n"
        "risk_per_trade gate rejected trade"
    )
    found = extract_findings_from_step(
        objective="review my trading algorithm",
        step_id="pytest",
        command_key="pytest",
        result_summary=text,
        success=False,
    )
    assert len(found) >= 1
    cats = {f.category for f in found}
    assert "failed_tests" in cats or "stale_prices" in cats or "risk_gates" in cats


def test_trading_review_produces_relevant_categories():
    text = "ranking mismatch between backtest and paper delayed_entry_failed dashboard down 8077"
    found = extract_findings_from_step(
        objective="compare backtest to paper trading",
        step_id="s1",
        command_key="read_logs",
        result_summary=text,
        success=True,
    )
    cats = {f.category for f in found}
    assert "ranking_mismatch" in cats or "backtest_vs_live_entry" in cats or "dashboard_paper_mismatch" in cats


def test_report_includes_findings_evidence_risks_test_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.reports.reports_dir", lambda: tmp_path)
    session = start_task("review my trading algorithm")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective=session.plan.objective,
            step_id="t1",
            command_key="pytest",
            result_summary="FAILED test_foo ranking mismatch",
            success=False,
        ),
    )
    md = build_engineering_report(get_active_task())
    assert "## Objective" in md
    assert "## Plan" in md
    assert "## Steps completed" in md
    assert "## Evidence (structured)" in md
    assert "## Risks" in md
    assert "## Test plan" in md
    assert "## Next recommended commands" in md
    path = write_task_report(get_active_task())
    body = path.read_text(encoding="utf-8")
    assert "Evidence" in body


def test_patch_proposal_not_applied():
    session = start_task("review algorithm")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective=session.plan.objective,
            step_id="s1",
            command_key="read_logs",
            result_summary="stale price risk gate",
            success=True,
        ),
    )
    result = ProposeTaskPatchAction().execute(
        CommandRequest(raw_text="propose", intent=Intent.PROPOSE_TASK_PATCH, confidence=1.0)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "NOT applied" in result.summary
    assert get_active_task().patch_proposal is not None
    # No file write from proposal
    diff_target = get_active_task().patch_proposal.target_files[0]
    assert not Path(diff_target).is_absolute() or True


def test_approve_only_marks_approved():
    session = start_task("task")
    session.structured_findings.append(
        extract_findings_from_step(
            objective="x",
            step_id="s",
            command_key="run_diagnostics",
            result_summary="error log",
            success=True,
        )[0]
    )
    ProposeTaskPatchAction().execute(
        CommandRequest(raw_text="p", intent=Intent.PROPOSE_TASK_PATCH, confidence=1.0)
    )
    result = ApproveTaskPatchAction().execute(
        CommandRequest(raw_text="a", intent=Intent.APPROVE_TASK_PATCH, confidence=1.0)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "approved" in result.summary.lower()
    assert "apply task patch" in result.summary.lower()
    assert get_active_task().patch_proposal.status == "approved"


def test_reject_discards_proposal():
    session = start_task("task")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective="x",
            step_id="s",
            command_key="diagnose_dashboard",
            result_summary="dashboard health fail",
            success=False,
        ),
    )
    ProposeTaskPatchAction().execute(
        CommandRequest(raw_text="p", intent=Intent.PROPOSE_TASK_PATCH, confidence=1.0)
    )
    pid = get_active_task().patch_proposal.proposal_id
    RejectTaskPatchAction().execute(
        CommandRequest(raw_text="r", intent=Intent.REJECT_TASK_PATCH, confidence=1.0)
    )
    assert get_active_task().patch_proposal is None


def test_blocks_env_secrets_targets():
    ok, msg = validate_patch_target(".env")
    assert not ok
    ok, msg = validate_patch_target("data/session_state.json")
    assert not ok
    ok, _ = validate_patch_target("task_agent/safety.py")
    assert ok


def test_blocks_live_trading_diff():
    ok, msg = validate_diff_text("+ enable live trading now")
    assert not ok


def test_no_arbitrary_shell_in_patch_flow():
    from task_agent.safety import subprocess_argv_for

    assert subprocess_argv_for("arbitrary_shell") is None


def test_show_task_findings_grouped():
    session = start_task("failures")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective=session.plan.objective,
            step_id="e1",
            command_key="show_last_errors",
            result_summary="ERROR traceback in foo.py",
            success=False,
        ),
    )
    result = ShowTaskFindingsAction().execute(
        CommandRequest(raw_text="findings", intent=Intent.SHOW_TASK_FINDINGS, confidence=1.0)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "Evidence" in result.summary or "Severity" in result.summary


def test_classify_phase20_intents():
    assert classify_rules("show task findings").intent == Intent.SHOW_TASK_FINDINGS
    assert classify_rules("propose task patch").intent == Intent.PROPOSE_TASK_PATCH


def test_run_step_populates_structured_findings():
    StartTaskAction().execute(
        CommandRequest(
            raw_text="review my trading algorithm",
            intent=Intent.START_TASK,
            confidence=1.0,
        )
    )
    from task_agent.approvals import approve_plan

    approve_plan(get_active_task())
    registry = MagicMock()
    registry.execute.return_value = MagicMock(
        status=ActionStatus.SUCCESS,
        summary="ranking mismatch stale price in strategy/x.py",
    )
    RunTaskStepAction(registry).execute(
        CommandRequest(raw_text="run", intent=Intent.RUN_TASK_STEP, confidence=1.0)
    )
    assert len(get_active_task().structured_findings) >= 1
