"""Execute allowlisted task steps only (supervised, one step per invocation)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from config import PROJECT_ROOT
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from task_agent.approvals import plan_is_approved, step_may_run
from task_agent.models import StepKind, StepStatus, TaskSession, TaskStatus
from task_agent.findings import extract_findings_from_step, merge_findings
from task_agent.reports import write_task_report
from task_agent.safety import (
    TASK_AGENT_MAX_RUNTIME_SECONDS,
    TASK_AGENT_MAX_STEPS,
    subprocess_argv_for,
    validate_command_key,
)

if TYPE_CHECKING:
    from actions.registry import ActionRegistry


def _capture_git_diff(cwd: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return (proc.stdout or proc.stderr or "").strip()[:4000]
    except Exception:
        return ""


def _run_subprocess_step(command_key: str, cwd: Path) -> CommandResult:
    from core.results import result_failed, result_success

    argv = subprocess_argv_for(command_key)
    if argv is None:
        return result_failed(Intent.UNKNOWN, f"No fixed argv for '{command_key}'.")
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=min(120, int(TASK_AGENT_MAX_RUNTIME_SECONDS)),
            check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        snippet = out.strip()[:2000] or "(no output)"
        if proc.returncode == 0:
            return result_success(Intent.UNKNOWN, f"{command_key} OK:\n{snippet}")
        return result_failed(Intent.UNKNOWN, f"{command_key} exit {proc.returncode}:\n{snippet}")
    except subprocess.TimeoutExpired:
        return result_failed(Intent.UNKNOWN, f"{command_key} timed out.")
    except Exception as exc:
        return result_failed(Intent.UNKNOWN, f"{command_key} failed: {exc}")


def _run_via_registry(command_key: str, registry: "ActionRegistry") -> CommandResult:
    from core.results import result_failed, result_success

    mapping: dict[str, tuple[Intent, dict]] = {
        "search_code": (Intent.SEARCH_CODE_TEXT, {"query": "strategy"}),
        "find_function": (Intent.FIND_FUNCTION, {"name": "run"}),
        "find_class": (Intent.FIND_CLASS, {"name": "PortfolioManager"}),
        "read_logs": (Intent.SEARCH_TRADING_LOGS, {"query": "error"}),
        "show_last_errors": (Intent.SHOW_LAST_ERRORS, {}),
        "run_diagnostics": (Intent.RUN_DIAGNOSTICS, {}),
        "diagnose_dashboard": (Intent.DIAGNOSE_DASHBOARD, {}),
        "diagnose_trading_loop": (Intent.DIAGNOSE_TRADING_LOOP, {}),
        "diagnose_recent_errors": (Intent.DIAGNOSE_RECENT_ERRORS, {}),
    }
    if command_key == "summarize_findings":
        return result_success(
            Intent.UNKNOWN,
            "Inspection findings aggregated into the task session.",
        )
    spec = mapping.get(command_key)
    if spec is None:
        return result_failed(Intent.UNKNOWN, f"No registry mapping for '{command_key}'.")
    intent, params = spec
    req = CommandRequest(
        raw_text=f"task:{command_key}",
        intent=intent,
        confidence=1.0,
        params=params,
    )
    return registry.execute(req)


def _next_pending_step(session: TaskSession):
    for step in session.plan.steps:
        if step.status == StepStatus.PENDING:
            return step
    return None


def run_next_step(
    session: TaskSession,
    registry: "ActionRegistry",
    *,
    step_id: str | None = None,
) -> tuple[CommandResult, TaskSession]:
    """Run at most one allowlisted step; never loops."""
    from core.results import (
        result_blocked,
        result_confirmation_required,
        result_success,
    )

    if session.stop_requested:
        return result_blocked(Intent.STOP_TASK, "Task stopped."), session

    if not plan_is_approved(session):
        return (
            result_confirmation_required(
                Intent.APPROVE_TASK_PLAN,
                "Approve the task plan before running steps.",
                "task_plan",
            ),
            session,
        )

    if session.steps_completed >= TASK_AGENT_MAX_STEPS:
        path = write_task_report(session)
        return (
            result_blocked(
                Intent.RUN_TASK_STEP,
                f"Max steps ({TASK_AGENT_MAX_STEPS}) reached. Report: {path}",
            ),
            session,
        )

    if time.monotonic() - session.started_at > TASK_AGENT_MAX_RUNTIME_SECONDS:
        path = write_task_report(session)
        return (
            result_blocked(
                Intent.RUN_TASK_STEP,
                f"Max runtime ({TASK_AGENT_MAX_RUNTIME_SECONDS}s) exceeded. Report: {path}",
            ),
            session,
        )

    if step_id:
        step = next((s for s in session.plan.steps if s.step_id == step_id), None)
    else:
        step = _next_pending_step(session)

    if step is None:
        path = write_task_report(session)
        return (
            result_success(
                Intent.SHOW_TASK_REPORT,
                f"All steps complete. Report: {path}",
            ),
            session,
        )

    verdict = validate_command_key(step.command_key)
    if not verdict.ok or step.kind == StepKind.BLOCKED:
        step.status = StepStatus.BLOCKED
        return result_blocked(Intent.RUN_TASK_STEP, verdict.reason or "Step blocked."), session

    ok, msg = step_may_run(session, step.step_id)
    if not ok:
        if step.requires_separate_approval:
            return (
                result_confirmation_required(
                    Intent.APPROVE_TASK_PLAN,
                    f"{msg} Approve step '{step.step_id}' then run again.",
                    step.step_id,
                ),
                session,
            )
        return result_blocked(Intent.RUN_TASK_STEP, msg), session

    if not session.git_diff_before:
        session.git_diff_before = _capture_git_diff(PROJECT_ROOT)

    session.status = TaskStatus.RUNNING
    step.status = StepStatus.RUNNING

    if step.kind == StepKind.CONFIRM_REQUIRED:
        step.status = StepStatus.NEEDS_APPROVAL
        return (
            result_confirmation_required(
                Intent.APPROVE_TASK_PLAN,
                f"Step '{step.step_id}' ({step.command_key}) requires separate approval.",
                step.step_id,
            ),
            session,
        )

    if step.command_key in ("pytest", "compileall"):
        result = _run_subprocess_step(step.command_key, PROJECT_ROOT)
    else:
        result = _run_via_registry(step.command_key, registry)

    success = result.status == ActionStatus.SUCCESS
    if success:
        step.status = StepStatus.DONE
        step.result_summary = (result.summary or "")[:500]
        if step.command_key != "summarize_findings":
            session.findings.append(f"{step.title}: {step.result_summary[:200]}")
        session.steps_completed += 1
        session.current_step_index += 1
    else:
        step.status = StepStatus.SKIPPED
        step.result_summary = (result.summary or "")[:500]

    new_findings = extract_findings_from_step(
        objective=session.plan.objective,
        step_id=step.step_id,
        command_key=step.command_key,
        result_summary=step.result_summary,
        success=success,
    )
    merge_findings(session.structured_findings, new_findings)

    session.git_diff_after = _capture_git_diff(PROJECT_ROOT)
    summary = f"Step '{step.step_id}' [{step.status.value}]: {step.result_summary[:800]}"
    return result_success(Intent.RUN_TASK_STEP, summary), session
