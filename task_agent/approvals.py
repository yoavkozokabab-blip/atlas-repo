"""Task plan and per-step approval tracking."""

from __future__ import annotations

from task_agent.models import StepKind, TaskSession, TaskStatus
from task_agent.safety import is_write_command


def approve_plan(session: TaskSession) -> None:
    session.plan_approved = True
    session.status = TaskStatus.APPROVED
    session.phase = session.phase  # stays until execute


def approve_step(session: TaskSession, step_id: str) -> bool:
    for step in session.plan.steps:
        if step.step_id == step_id:
            session.approved_step_ids.add(step_id)
            return True
    return False


def plan_is_approved(session: TaskSession) -> bool:
    return session.plan_approved


def step_may_run(session: TaskSession, step_id: str) -> tuple[bool, str]:
    if not plan_is_approved(session):
        return False, "Task plan not approved. Say 'approve task plan' first."
    if session.stop_requested:
        return False, "Task stop requested."
    step = next((s for s in session.plan.steps if s.step_id == step_id), None)
    if step is None:
        return False, f"Unknown step '{step_id}'."
    if step.kind == StepKind.BLOCKED:
        return False, f"Step '{step_id}' is blocked."
    if step.requires_separate_approval and step_id not in session.approved_step_ids:
        return False, f"Step '{step_id}' requires separate approval before running."
    return True, ""


def approval_hint_for_step(step_id: str) -> str:
    if is_write_command(step_id):
        return f"Approve step '{step_id}' via approve task plan with step_id."
    return ""
