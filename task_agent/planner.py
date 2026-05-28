"""Build supervised TaskPlan from user objective (no execution)."""

from __future__ import annotations

import re

from task_agent.models import StepKind, StepStatus, TaskPlan, TaskStep
from task_agent.safety import (
    CONFIRM_COMMAND_KEYS,
    READONLY_COMMAND_KEYS,
    classify_command_key,
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "task"


def _step(
    step_id: str,
    title: str,
    command_key: str,
    *,
    description: str = "",
    params: dict | None = None,
) -> TaskStep:
    kind = classify_command_key(command_key)
    return TaskStep(
        step_id=step_id,
        title=title,
        kind=kind,
        command_key=command_key,
        description=description,
        params=params or {},
        requires_separate_approval=kind == StepKind.CONFIRM_REQUIRED,
    )


def _template_trading_algorithm(objective: str) -> TaskPlan:
    steps = [
        _step("inspect_code", "Search trading codebase for algorithm entry points", "search_code"),
        _step("find_risk", "Find risk and position sizing usage", "find_function", params={"name": "risk"}),
        _step("read_logs", "Read recent trading logs for errors", "read_logs"),
        _step("diagnose", "Run system diagnostics", "run_diagnostics"),
        _step("pytest", "Run pytest (read-only validation)", "pytest"),
        _step("compile", "Run compileall syntax check", "compileall"),
        _step("summarize", "Summarize inspection findings", "summarize_findings"),
    ]
    return TaskPlan(
        objective=objective,
        assumptions=[
            "Analysis is read-only until explicit write approval.",
            "Trading project root from TRADING_PROJECT_ROOT config.",
            "No live execution or fund movement.",
        ],
        steps=steps,
        required_approvals=["Plan approval before any step", "Separate approval per write/edit step"],
        files_likely_needed=[
            "strategy modules under trading project",
            "reports/live_paper logs",
            "config risk keys",
        ],
        allowed_commands=sorted(READONLY_COMMAND_KEYS | CONFIRM_COMMAND_KEYS),
    )


def _template_dashboard_down(objective: str) -> TaskPlan:
    steps = [
        _step("dash_health", "Check dashboard health endpoint", "diagnose_dashboard"),
        _step("diag", "Run JARVIS diagnostics", "run_diagnostics"),
        _step("errors", "Show last errors from logs", "show_last_errors"),
        _step("summarize", "Summarize investigation", "summarize_findings"),
    ]
    return TaskPlan(
        objective=objective,
        assumptions=["Dashboard URL is fixed localhost allowlist only.", "No browser automation."],
        steps=steps,
        required_approvals=["Plan approval"],
        files_likely_needed=["trading dashboard scripts", "scheduled_logs"],
        allowed_commands=sorted(READONLY_COMMAND_KEYS),
    )


def _template_backtest_paper(objective: str) -> TaskPlan:
    steps = [
        _step("reports", "Show latest live paper report", "read_logs"),
        _step("history", "Review recent trading history", "read_logs"),
        _step("rejects", "Inspect rejection reasons", "read_logs"),
        _step("diag_loop", "Diagnose trading loop status", "diagnose_trading_loop"),
        _step("summarize", "Compare backtest vs paper findings", "summarize_findings"),
        _step(
            "backtest",
            "Run long backtest (requires approval)",
            "run_long_backtest",
            description="Blocked until separate approval.",
        ),
    ]
    return TaskPlan(
        objective=objective,
        assumptions=["Comparison is report-only unless backtest approved."],
        steps=steps,
        required_approvals=["Plan approval", "Approval for run_long_backtest"],
        files_likely_needed=["reports/live_paper", "backtest outputs"],
        allowed_commands=sorted(READONLY_COMMAND_KEYS | {"run_long_backtest"}),
    )


def _template_failure_report(objective: str) -> TaskPlan:
    steps = [
        _step("errors", "Show last errors", "show_last_errors"),
        _step("recent", "Diagnose recent errors", "diagnose_recent_errors"),
        _step("logs", "Search trading logs", "read_logs"),
        _step("summarize", "Build failure summary", "summarize_findings"),
    ]
    return TaskPlan(
        objective=objective,
        assumptions=["Report only — no file writes without approval."],
        steps=steps,
        required_approvals=["Plan approval"],
        files_likely_needed=["reports/live_paper/scheduled_logs"],
        allowed_commands=sorted(READONLY_COMMAND_KEYS),
    )


def _template_generic(objective: str) -> TaskPlan:
    steps = [
        _step("inspect", "Inspect via diagnostics", "run_diagnostics"),
        _step("search", "Search codebase", "search_code"),
        _step("pytest", "Run pytest", "pytest"),
        _step("summarize", "Summarize findings", "summarize_findings"),
    ]
    return TaskPlan(
        objective=objective,
        assumptions=["Generic supervised task — read-only first."],
        steps=steps,
        required_approvals=["Plan approval"],
        files_likely_needed=["project source and logs"],
        allowed_commands=sorted(READONLY_COMMAND_KEYS),
    )


def create_plan_from_objective(objective: str) -> TaskPlan:
    """Create a TaskPlan from natural language (classification only)."""
    text = (objective or "").strip()
    lower = text.lower()

    if any(k in lower for k in ("algorithm", "strategy", "trading algo", "review my trading")):
        return _template_trading_algorithm(text)
    if any(k in lower for k in ("dashboard", "down", "not running", "8077")):
        return _template_dashboard_down(text)
    if any(k in lower for k in ("backtest", "paper", "compare")):
        return _template_backtest_paper(text)
    if any(k in lower for k in ("failure", "failed", "errors", "report")):
        return _template_failure_report(text)
    return _template_generic(text)
