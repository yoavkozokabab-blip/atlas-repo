"""Autonomous Agent Stack v1 — router-facing actions.

Exposes exactly six commands (and only these):
  plan autonomous task <goal>      preview a bounded plan (no execution)
  run autonomous task <goal>       execute (approval-gated, pinned plan)
  research deeply <goal>           execute research mode (approval-gated)
  compare sources for <goal>       execute compare mode (approval-gated)
  show last autonomous run         read-only
  show autonomous audit <task_id>  read-only

Safety:
  * Forbidden goals are rejected before any plan exists -> BLOCKED + audited.
  * run/research/compare are two-phase with PINNED-PLAN approval: first call
    builds + pins the plan (by hash) and returns CONFIRMATION_REQUIRED with the
    full preview; on "yes" the EXACT pinned plan (hash-checked) executes via the
    real AutonomousBrowserProvider. Unavailable provider -> BLOCKED (no mock).
"""

from __future__ import annotations

from typing import Callable

from actions.base import BaseAction
from core.results import result_blocked, result_confirmation_required, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent

# Provider injection seam (tests override; production builds a real browser).
_provider_factory: Callable[[], object] | None = None


def set_autonomy_provider_factory(factory: Callable[[], object] | None) -> None:
    global _provider_factory
    _provider_factory = factory


def _make_provider():
    if _provider_factory is not None:
        return _provider_factory()
    from autonomy.provider import AutonomousBrowserProvider

    return AutonomousBrowserProvider(headless=True)


def _extract_goal(request: CommandRequest, markers: tuple[str, ...]) -> str:
    goal = str(request.params.get("goal") or "").strip()
    if goal:
        return goal
    raw = request.raw_text or ""
    low = raw.lower()
    for marker in markers:
        i = low.find(marker)
        if i != -1:
            return raw[i + len(marker):].strip()
    return raw.strip()


_SAFETY_BANNER = (
    "This autonomous run is READ-ONLY: it will search and open public web pages "
    "and summarize them. It will NOT log in, submit forms, buy, book, order, "
    "download, delete, or send anything. Bounded by the limits shown above."
)


def _build_and_confirm(request: CommandRequest, *, mode: str, intent: Intent,
                       markers: tuple[str, ...]) -> CommandResult:
    """Phase 1 (build+pin+preview) or Phase 2 (execute pinned) for run-style intents."""
    from core import confirmation
    from autonomy import audit, pending
    from autonomy.planner import build_research_plan
    from autonomy.task import AutonomousTask, TaskStatus
    from tooluse.contracts import ForbiddenGoalError

    # ---- Phase 2: confirmed -> execute exact pinned plan ----
    if request.confirmed:
        pinned = pending.get_pinned(request.confirmation_id or "")
        if pinned is None:
            return result_failed(intent, "Approved plan not found (expired). Please re-issue the command.")
        task, plan = pinned
        return _execute(task, plan, intent)

    # ---- Phase 1: build + pin + request approval ----
    goal = _extract_goal(request, markers)
    if not goal:
        return result_failed(intent, "What should the autonomous task accomplish?")
    try:
        plan = build_research_plan(goal, mode=mode)
    except ForbiddenGoalError as exc:
        from autonomy.capabilities import detect_forbidden
        audit.record_blocked(goal, str(exc), intent=intent.value, detected=detect_forbidden(goal))
        return result_blocked(intent, str(exc))

    task = AutonomousTask(
        user_goal=goal,
        normalized_goal=plan.normalized_goal,
        safety_class=plan.safety_class.value,
        allowed_capabilities=list(plan.allowed_capabilities),
        forbidden_capabilities_detected=[],
        status=TaskStatus.AWAITING_APPROVAL,
    )
    cid = confirmation.create_confirmation(
        intent.value, {"raw_text": request.raw_text, "params": dict(request.params)},
    )
    task.plan_id = cid
    task.approved_plan_hash = plan.plan_hash   # pinned: approved == executed
    pending.pin(cid, task, plan)
    body = (
        f"{plan.format()}\n\n{_SAFETY_BANNER}\n"
        f"Reply yes/confirm to run this exact plan, or no/cancel to abort (id: {cid})."
    )
    return result_confirmation_required(intent, body, cid)


def _execute(task, plan, intent: Intent) -> CommandResult:
    from autonomy import audit, pending
    from autonomy.executor import AutonomousExecutor
    from autonomy.task import TaskStatus

    task.status = TaskStatus.APPROVED
    provider = _make_provider()
    try:
        completed = AutonomousExecutor(provider).run(task, plan)
    finally:
        try:
            provider.close()
        except Exception:
            pass

    pending.set_last_task(completed)
    pending.discard(task.plan_id)
    audit.record_run(completed, plan, safety_blocks=task.forbidden_capabilities_detected)

    body = f"{completed.final_report}\n\n[status: {completed.status.value} | confidence: {completed.confidence:.2f} | task_id: {completed.task_id}]"
    if completed.status in (TaskStatus.SUCCESS, TaskStatus.PARTIAL):
        return result_success(intent, body, data={"task_id": completed.task_id, "status": completed.status.value})
    if completed.status == TaskStatus.BLOCKED_UNAVAILABLE:
        return result_blocked(intent, body + "\n\nNo real browser provider — nothing executed.")
    if completed.status == TaskStatus.BLOCKED_FORBIDDEN:
        return result_blocked(intent, body)
    return result_failed(intent, body, error=f"autonomous run {completed.status.value}")


class PlanAutonomousTaskAction(BaseAction):
    intent = Intent.PLAN_AUTONOMOUS_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from autonomy.planner import build_research_plan
        from autonomy.capabilities import detect_forbidden
        from autonomy import audit
        from tooluse.contracts import ForbiddenGoalError

        goal = _extract_goal(request, ("plan autonomous task",))
        if not goal:
            return result_failed(Intent.PLAN_AUTONOMOUS_TASK, "What should the autonomous task accomplish?")
        try:
            plan = build_research_plan(goal)
        except ForbiddenGoalError as exc:
            audit.record_blocked(goal, str(exc), intent="plan_autonomous_task", detected=detect_forbidden(goal))
            return result_blocked(Intent.PLAN_AUTONOMOUS_TASK, str(exc))
        body = f"{plan.format()}\n\n{_SAFETY_BANNER}\nTo execute: run autonomous task {goal}"
        return result_success(Intent.PLAN_AUTONOMOUS_TASK, body, data={"read_only": True, "dry_run": True})


class RunAutonomousTaskAction(BaseAction):
    intent = Intent.RUN_AUTONOMOUS_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _build_and_confirm(request, mode="research", intent=Intent.RUN_AUTONOMOUS_TASK,
                                  markers=("run autonomous task",))


class ResearchDeeplyAction(BaseAction):
    intent = Intent.RESEARCH_DEEPLY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _build_and_confirm(request, mode="research", intent=Intent.RESEARCH_DEEPLY,
                                  markers=("research deeply",))


class CompareSourcesForAction(BaseAction):
    intent = Intent.COMPARE_SOURCES_FOR.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _build_and_confirm(request, mode="compare", intent=Intent.COMPARE_SOURCES_FOR,
                                  markers=("compare sources for",))


class ShowLastAutonomousRunAction(BaseAction):
    intent = Intent.SHOW_LAST_AUTONOMOUS_RUN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from autonomy import pending

        task = pending.get_last_task()
        if task is None:
            return result_success(Intent.SHOW_LAST_AUTONOMOUS_RUN,
                                  "No autonomous run recorded yet. Try: run autonomous task <goal>",
                                  data={"read_only": True})
        body = f"{task.final_report}\n\n[status: {task.status.value} | confidence: {task.confidence:.2f} | task_id: {task.task_id}]"
        return result_success(Intent.SHOW_LAST_AUTONOMOUS_RUN, body, data={"read_only": True})


class ShowAutonomousAuditAction(BaseAction):
    intent = Intent.SHOW_AUTONOMOUS_AUDIT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        import json
        from pathlib import Path
        from config import PROJECT_ROOT

        task_id = str(request.params.get("task_id") or "").strip()
        if not task_id:
            return result_failed(Intent.SHOW_AUTONOMOUS_AUDIT, "Usage: show autonomous audit <task_id>")
        # Read-only display of the stored audit json (no execution).
        path = Path(PROJECT_ROOT) / "reports" / "autonomous_runs" / f"{task_id}.json"
        if not path.is_file():
            return result_failed(Intent.SHOW_AUTONOMOUS_AUDIT, f"No audit found for task_id {task_id}.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return result_failed(Intent.SHOW_AUTONOMOUS_AUDIT, f"Could not read audit: {exc}")
        lines = [
            f"Autonomous audit {task_id}:",
            f"  status: {data.get('status')}",
            f"  goal: {data.get('user_goal')}",
            f"  plan_hash: {data.get('plan_hash')}",
            f"  confidence: {data.get('confidence')}",
            f"  urls_opened: {len(data.get('urls_opened', []))}",
            f"  steps: {len(data.get('step_results', []))}",
            f"  safety_blocks: {data.get('safety_blocks')}",
        ]
        return result_success(Intent.SHOW_AUTONOMOUS_AUDIT, "\n".join(lines), data={"read_only": True})
