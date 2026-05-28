"""Supervised task agent actions (Phase 19)."""

from __future__ import annotations

import re

from actions.base import BaseAction
from core.results import result_blocked, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from task_agent.approvals import approve_plan, approve_step, plan_is_approved
from task_agent.executor import run_next_step
from task_agent.findings import format_findings_grouped
from config import PATCH_APPLY_ENABLED
from task_agent.patch_apply import (
    apply_approved_patch,
    get_last_apply,
    reset_patch_apply_store,
    rollback_last_patch,
)
from task_agent.patch_proposals import (
    approve_proposal,
    build_patch_proposal,
    format_patch_proposal,
    reject_proposal,
)
from task_agent.reports import write_task_report
from task_agent.session import get_active_task, start_task, stop_task
from task_agent.safety import validate_command_key


def _objective_from_request(request: CommandRequest) -> str:
    obj = (request.params.get("objective") or request.params.get("task") or "").strip()
    if obj:
        return obj
    raw = (request.raw_text or "").strip()
    for prefix in (
        r"^start\s+task\s+",
        r"^jarvis\s+",
        r"^please\s+",
    ):
        raw = re.sub(prefix, "", raw, flags=re.I).strip()
    return raw or "Supervised inspection task"


class StartTaskAction(BaseAction):
    intent = Intent.START_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        objective = _objective_from_request(request)
        session = start_task(objective)
        summary = (
            f"Task '{session.task_id}' planned (not executed).\n"
            f"Status: {session.status.value}\n\n"
            f"{session.plan.format_plan()}\n\n"
            "Say 'approve task plan' then 'run task step' for each step."
        )
        return result_success(
            Intent.START_TASK,
            summary,
            data={"task_id": session.task_id, "steps": len(session.plan.steps)},
        )


class ShowTaskPlanAction(BaseAction):
    intent = Intent.SHOW_TASK_PLAN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(
                Intent.SHOW_TASK_PLAN,
                "No active task. Start one with e.g. 'review my trading algorithm'.",
            )
        return result_success(
            Intent.SHOW_TASK_PLAN,
            session.plan.format_plan(),
            data={"task_id": session.task_id},
        )


class ApproveTaskPlanAction(BaseAction):
    intent = Intent.APPROVE_TASK_PLAN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        session = get_active_task()
        if session is None:
            return result_failed(Intent.APPROVE_TASK_PLAN, "No active task to approve.")
        step_id = (request.params.get("step_id") or "").strip()
        if step_id:
            if not approve_step(session, step_id):
                return result_failed(
                    Intent.APPROVE_TASK_PLAN,
                    f"Unknown step '{step_id}'.",
                )
            return result_success(
                Intent.APPROVE_TASK_PLAN,
                f"Step '{step_id}' approved for execution.",
            )
        approve_plan(session)
        return result_success(
            Intent.APPROVE_TASK_PLAN,
            f"Task plan '{session.task_id}' approved. Run steps with 'run task step'.",
        )


class RunTaskStepAction(BaseAction):
    intent = Intent.RUN_TASK_STEP.value

    def __init__(self, registry=None) -> None:
        self._registry = registry

    def _registry_or_default(self):
        if self._registry is not None:
            return self._registry
        from actions.registry import ActionRegistry

        return ActionRegistry()

    def execute(self, request: CommandRequest) -> CommandResult:
        session = get_active_task()
        if session is None:
            return result_failed(Intent.RUN_TASK_STEP, "No active task.")
        step_id = (request.params.get("step_id") or "").strip() or None
        result, _session = run_next_step(
            session,
            self._registry_or_default(),
            step_id=step_id,
        )
        return result


class StopTaskAction(BaseAction):
    intent = Intent.STOP_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = stop_task()
        if session is None:
            return result_failed(Intent.STOP_TASK, "No active task to stop.")
        return result_success(
            Intent.STOP_TASK,
            f"Task '{session.task_id}' stop requested.",
        )


class ShowTaskStatusAction(BaseAction):
    intent = Intent.SHOW_TASK_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_success(Intent.SHOW_TASK_STATUS, "No active supervised task.")
        pending = sum(1 for s in session.plan.steps if s.status.value == "pending")
        done = sum(1 for s in session.plan.steps if s.status.value == "done")
        patch_note = "(none)"
        if session.patch_proposal:
            patch_note = f"{session.patch_proposal.proposal_id} [{session.patch_proposal.status}]"
        lines = [
            f"Task: {session.task_id}",
            f"Status: {session.status.value}",
            f"Plan approved: {plan_is_approved(session)}",
            f"Stop requested: {session.stop_requested}",
            f"Steps done/pending: {done}/{pending}",
            f"Steps completed count: {session.steps_completed}",
            f"Structured findings: {len(session.structured_findings)}",
            f"Patch proposal: {patch_note}",
            f"Report: {session.report_path or '(not written)'}",
        ]
        return result_success(Intent.SHOW_TASK_STATUS, "\n".join(lines))


class ShowTaskReportAction(BaseAction):
    intent = Intent.SHOW_TASK_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.SHOW_TASK_REPORT, "No active task.")
        if not session.report_path:
            path = write_task_report(session)
        else:
            from pathlib import Path

            path = Path(session.report_path)
            if not path.is_file():
                path = write_task_report(session)
        body = path.read_text(encoding="utf-8")[:8000]
        return result_success(
            Intent.SHOW_TASK_REPORT,
            f"Report: {path}\n\n{body}",
            data={"path": str(path)},
        )


class ShowTaskFindingsAction(BaseAction):
    intent = Intent.SHOW_TASK_FINDINGS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.SHOW_TASK_FINDINGS, "No active task.")
        body = format_findings_grouped(session.structured_findings)
        return result_success(Intent.SHOW_TASK_FINDINGS, body)


class ProposeTaskPatchAction(BaseAction):
    intent = Intent.PROPOSE_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.PROPOSE_TASK_PATCH, "No active task.")
        if not session.structured_findings:
            return result_failed(
                Intent.PROPOSE_TASK_PATCH,
                "No findings yet. Run task steps first.",
            )
        proposal = build_patch_proposal(
            objective=session.plan.objective,
            findings=session.structured_findings,
        )
        if proposal is None:
            return result_blocked(
                Intent.PROPOSE_TASK_PATCH,
                "Could not build a safe patch proposal from findings.",
            )
        session.patch_proposal = proposal
        summary = format_patch_proposal(proposal)
        return result_success(
            Intent.PROPOSE_TASK_PATCH,
            summary,
            data={"proposal_id": proposal.proposal_id},
        )


class ShowTaskPatchAction(BaseAction):
    intent = Intent.SHOW_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.SHOW_TASK_PATCH, "No active task.")
        if session.patch_proposal is None:
            return result_failed(
                Intent.SHOW_TASK_PATCH,
                "No patch proposal. Use 'propose task patch' first.",
            )
        return result_success(
            Intent.SHOW_TASK_PATCH,
            format_patch_proposal(session.patch_proposal),
        )


class ApproveTaskPatchAction(BaseAction):
    intent = Intent.APPROVE_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.APPROVE_TASK_PATCH, "No active task.")
        proposal = session.patch_proposal
        if proposal is None:
            return result_failed(Intent.APPROVE_TASK_PATCH, "No patch to approve.")
        if proposal.status == "rejected":
            return result_failed(Intent.APPROVE_TASK_PATCH, "Proposal was rejected.")
        approve_proposal(proposal)
        return result_success(
            Intent.APPROVE_TASK_PATCH,
            f"Patch '{proposal.proposal_id}' marked approved. "
            "Say 'apply task patch' (with confirmation) to apply safely.",
        )


class RejectTaskPatchAction(BaseAction):
    intent = Intent.REJECT_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = get_active_task()
        if session is None:
            return result_failed(Intent.REJECT_TASK_PATCH, "No active task.")
        proposal = session.patch_proposal
        if proposal is None:
            return result_failed(Intent.REJECT_TASK_PATCH, "No patch to reject.")
        reject_proposal(proposal)
        session.patch_proposal = None
        return result_success(
            Intent.REJECT_TASK_PATCH,
            f"Patch proposal '{proposal.proposal_id}' discarded.",
        )


class ApplyTaskPatchAction(BaseAction):
    intent = Intent.APPLY_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not PATCH_APPLY_ENABLED:
            return result_blocked(Intent.APPLY_TASK_PATCH, "Patch apply is disabled in config.")
        session = get_active_task()
        if session is None:
            return result_failed(Intent.APPLY_TASK_PATCH, "No active task.")
        proposal = session.patch_proposal
        if proposal is None or proposal.status != "approved":
            return result_failed(
                Intent.APPLY_TASK_PATCH,
                "Patch must be proposed and approved first.",
            )
        state, summary = apply_approved_patch(proposal)
        session.patch_backup_dir = str(state.backup_dir or "")
        session.patch_applied = state.applied
        session.git_diff_after = state.git_diff
        if not state.applied:
            return result_failed(Intent.APPLY_TASK_PATCH, summary)
        return result_success(
            Intent.APPLY_TASK_PATCH,
            summary,
            data={"apply_id": state.apply_id, "backup": str(state.backup_dir)},
        )


class RollbackTaskPatchAction(BaseAction):
    intent = Intent.ROLLBACK_TASK_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        ok, msg = rollback_last_patch()
        if not ok:
            return result_failed(Intent.ROLLBACK_TASK_PATCH, msg)
        return result_success(Intent.ROLLBACK_TASK_PATCH, msg)


class ShowLastDiffAction(BaseAction):
    intent = Intent.SHOW_LAST_DIFF.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        state = get_last_apply()
        if state is None or not state.git_diff:
            return result_failed(Intent.SHOW_LAST_DIFF, "No patch apply recorded yet.")
        return result_success(
            Intent.SHOW_LAST_DIFF,
            f"Last git diff:\n{state.git_diff}",
        )


def validate_task_command(command_key: str) -> CommandResult | None:
    """Helper for tests — returns blocked result if invalid."""
    v = validate_command_key(command_key)
    if v.ok:
        return None
    return result_blocked(Intent.RUN_TASK_STEP, v.reason)
