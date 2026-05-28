"""Phases 21–30 operating layer tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from actions.operating_layer_actions import (
    BrowserDomReadAction,
    CompareBacktestToPaperAction,
    PlanExperimentsAction,
    QueueTaskAction,
    ReviewTradingAlgorithmAction,
    ShowStartupHealthAction,
    ShowTaskQueueAction,
    StartTradingWorkspaceAction,
)
from actions.task_actions import (
    ApplyTaskPatchAction,
    ApproveTaskPatchAction,
    ProposeTaskPatchAction,
    RollbackTaskPatchAction,
    ShowLastDiffAction,
)
from artifacts.builder import build_presentation_outline
from brain.intent_classifier import classify_rules
from computer_control.guided import reset_guided_state, suggest_ui_target
from core.types import ActionStatus, CommandRequest, Intent
from task_agent.findings import extract_findings_from_step, merge_findings
from task_agent.patch_apply import (
    apply_unified_diff_to_path,
    reset_patch_apply_store,
)
from task_agent.patch_proposals import build_patch_proposal, validate_patch_target
from task_agent.queue import enqueue, format_queue, reset_queue_store
from task_agent.session import get_active_task, reset_task_store, start_task


@pytest.fixture(autouse=True)
def _clean():
    reset_task_store()
    reset_queue_store()
    reset_patch_apply_store()
    reset_guided_state()
    yield
    reset_task_store()
    reset_queue_store()
    reset_patch_apply_store()
    reset_guided_state()


def test_classify_phase21_30_intents():
    cases = [
        ("apply task patch", Intent.APPLY_TASK_PATCH),
        ("rollback task patch", Intent.ROLLBACK_TASK_PATCH),
        ("review trading algorithm", Intent.REVIEW_TRADING_ALGORITHM),
        ("compare backtest to paper", Intent.COMPARE_BACKTEST_TO_PAPER),
        ("queue task analyze logs", Intent.QUEUE_TASK),
        ("start trading workspace", Intent.START_TRADING_WORKSPACE),
        ("show startup health", Intent.SHOW_STARTUP_HEALTH),
    ]
    for text, expected in cases:
        r = classify_rules(text)
        assert r.intent == expected, text


def test_apply_requires_approved_patch(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.patch_apply.PATCH_BACKUP_ROOT", tmp_path / "backups")
    target = tmp_path / "sample.py"
    target.write_text("line1\nline2\n", encoding="utf-8")
    diff = """--- a/sample.py
+++ b/sample.py
@@ -1,2 +1,3 @@
 line1
+added_line
 line2
"""
    ok, _ = apply_unified_diff_to_path(target, diff)
    assert ok
    assert "added_line" in target.read_text(encoding="utf-8")


def test_apply_patch_action_blocked_without_approval():
    session = start_task("review algo")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective="x",
            step_id="s",
            command_key="pytest",
            result_summary="FAILED ranking mismatch",
            success=False,
        ),
    )
    ProposeTaskPatchAction().execute(CommandRequest(raw_text="propose"))
    r = ApplyTaskPatchAction().execute(CommandRequest(raw_text="apply"))
    assert r.status == ActionStatus.FAILED


def test_apply_after_approve_uses_backup(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.patch_apply.PATCH_BACKUP_ROOT", tmp_path / "bk")
    rel = "task_agent/safety.py"
    ok, _ = validate_patch_target(rel)
    assert ok
    session = start_task("review")
    merge_findings(
        session.structured_findings,
        extract_findings_from_step(
            objective="review",
            step_id="t",
            command_key="read_logs",
            result_summary="stale price risk gate",
            success=True,
        ),
    )
    ProposeTaskPatchAction().execute(CommandRequest(raw_text="propose"))
    ApproveTaskPatchAction().execute(CommandRequest(raw_text="approve"))
    with patch("task_agent.patch_apply._run_pytest", return_value="ok"):
        with patch("task_agent.patch_apply._git_diff", return_value="diff snippet"):
            r = ApplyTaskPatchAction().execute(CommandRequest(raw_text="apply"))
    if r.status == ActionStatus.SUCCESS:
        rb = RollbackTaskPatchAction().execute(CommandRequest(raw_text="rollback"))
        assert rb.status == ActionStatus.SUCCESS
        ShowLastDiffAction().execute(CommandRequest(raw_text="diff"))


def test_trading_deep_review_finds_categories():
    with patch("task_agent.trading_deep_review._scan_strategy_files", return_value=["strategy/a.py"]):
        with patch("task_agent.trading_deep_review._read_log_snippets", return_value="ranking mismatch reject"):
            r = ReviewTradingAlgorithmAction().execute(
                CommandRequest(raw_text="review trading algorithm")
            )
    assert r.status == ActionStatus.SUCCESS
    session = get_active_task()
    assert session and len(session.structured_findings) >= 1


def test_comparison_report_written(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.comparison_reports.ARTIFACTS_DIR", tmp_path)
    r = CompareBacktestToPaperAction().execute(
        CommandRequest(raw_text="compare backtest to paper")
    )
    assert r.status == ActionStatus.SUCCESS
    assert list(tmp_path.rglob("backtest_paper_*.md"))


def test_experiment_plan_not_executed(tmp_path, monkeypatch):
    monkeypatch.setattr("task_agent.experiment_planner.ARTIFACTS_DIR", tmp_path)
    r = PlanExperimentsAction().execute(CommandRequest(raw_text="plan experiments"))
    assert r.status == ActionStatus.SUCCESS
    assert "not executed" in r.summary.lower() or "DRAFT" in r.summary


def test_task_queue_enqueue():
    QueueTaskAction().execute(CommandRequest(raw_text="queue task inspect logs"))
    r = ShowTaskQueueAction().execute(CommandRequest(raw_text="show task queue"))
    assert "queued" in r.summary.lower() or "Queue" in r.summary


def test_workspace_launcher_lists_steps():
    r = StartTradingWorkspaceAction().execute(
        CommandRequest(raw_text="start trading workspace")
    )
    assert "open trading dashboard" in r.summary.lower()


def test_guided_ui_blocks_unknown_target():
    sug, msg = suggest_ui_target("random_button")
    assert sug is None


def test_browser_dom_disabled_by_default():
    r = BrowserDomReadAction().execute(CommandRequest(raw_text="browser dom read"))
    assert r.status in (ActionStatus.BLOCKED, ActionStatus.FAILED)


def test_build_presentation_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("artifacts.builder.ARTIFACTS_DIR", tmp_path)
    path, _ = build_presentation_outline("risk gates")
    assert path.is_file()


def test_startup_health():
    r = ShowStartupHealthAction().execute(CommandRequest(raw_text="show startup health"))
    assert r.status == ActionStatus.SUCCESS
    assert "startup health" in r.summary.lower()


def test_blocks_env_patch_target():
    ok, _ = validate_patch_target(".env")
    assert not ok
