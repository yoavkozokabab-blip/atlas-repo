"""Phase 72 — router-facing actions for bounded, read-only tool use.

Exposes exactly three commands:
  - plan_tool_task <goal>      preview the dry-run plan (no execution, no approval)
  - run_tool_task <goal>       execute search->open->summarize (approval-gated)
  - show_last_tool_run         read-only display of the last run

Safety model:
  * The planner rejects forbidden goals (payments/orders/bookings/submits/
    logins/downloads/deletes/sends) before any plan exists -> BLOCKED + audited.
  * run_tool_task is two-phase and PINNED: the first call builds + pins the plan
    and returns CONFIRMATION_REQUIRED with the full plan preview; on "yes" the
    EXACT pinned plan is executed (previewed == executed).
  * Execution uses the real PlaywrightBrowserProvider (no mock branch); an
    unavailable provider yields BLOCKED_UNAVAILABLE, never success.
  * Every run and every blocked attempt is written to data/tool_use_audit.jsonl.
"""

from __future__ import annotations

import time
from typing import Callable

from actions.base import BaseAction
from core.results import result_blocked, result_confirmation_required, result_failed, result_success
from core.types import ActionStatus, CommandRequest, CommandResult, Intent

# --- provider injection seam (tests override; production builds a real browser) ---
_provider_factory: Callable[[], object] | None = None


def set_tool_provider_factory(factory: Callable[[], object] | None) -> None:
    """Override the provider factory (tests). None = real PlaywrightBrowserProvider."""
    global _provider_factory
    _provider_factory = factory


def _make_provider():
    if _provider_factory is not None:
        return _provider_factory()
    from tooluse.provider import PlaywrightBrowserProvider

    return PlaywrightBrowserProvider(headless=True)


def _extract_goal(request: CommandRequest) -> str:
    goal = str(request.params.get("goal") or "").strip()
    if goal:
        return goal
    raw = request.raw_text or ""
    low = raw.lower()
    for marker in ("run tool task", "plan tool task", "preview web task", "research", "look up"):
        i = low.find(marker)
        if i != -1:
            goal = raw[i + len(marker):].strip()
            for suffix in (" and summarize", " and summarise"):
                if goal.lower().endswith(suffix):
                    goal = goal[: -len(suffix)].strip()
            return goal
    return raw.strip()


def _plan_hash(plan) -> str:
    import hashlib

    return hashlib.sha256(plan.format().encode("utf-8", "ignore")).hexdigest()[:16]


_SAFETY_BANNER = (
    "This will open a REAL browser and visit external web pages. Read-only: it "
    "will NOT log in, submit forms, buy, book, order, or download."
)
_UNTRUSTED_PROVIDER_LABELS = {"mock", "unavailable", "degraded", "simulated"}


def _run_has_untrusted_provider(run) -> bool:
    for step in run.steps:
        provider = ((step.observation.provider if step.observation else "") or "").strip().lower()
        if provider in _UNTRUSTED_PROVIDER_LABELS:
            return True
    return False


class PlanToolTaskAction(BaseAction):
    """Preview the dry-run plan only. Executes nothing; needs no approval."""

    intent = Intent.PLAN_TOOL_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from tooluse.contracts import ForbiddenGoalError
        from tooluse.planner import build_search_open_summarize_plan
        from tooluse import audit

        goal = _extract_goal(request)
        if not goal:
            return result_failed(Intent.PLAN_TOOL_TASK, "What should the tool task accomplish?")
        try:
            plan = build_search_open_summarize_plan(goal)
        except ForbiddenGoalError as exc:
            audit.record_blocked(goal, str(exc), intent="plan_tool_task")
            return result_blocked(Intent.PLAN_TOOL_TASK, str(exc))
        body = f"{plan.format()}\n\n{_SAFETY_BANNER}\nTo execute: run tool task {goal}"
        return result_success(Intent.PLAN_TOOL_TASK, body, data={"read_only": True, "dry_run": True})


class RunToolTaskAction(BaseAction):
    """Two-phase, pinned-plan, approval-gated bounded tool run."""

    intent = Intent.RUN_TOOL_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from core import confirmation
        from tooluse import audit, pending
        from tooluse.contracts import ForbiddenGoalError
        from tooluse.planner import build_search_open_summarize_plan

        goal = _extract_goal(request)

        # ---- Phase 2: confirmed -> execute the EXACT pinned plan ----
        if request.confirmed:
            plan_id = request.confirmation_id or ""
            plan = pending.get_pinned_plan(plan_id)
            if plan is None:
                return result_failed(
                    Intent.RUN_TOOL_TASK,
                    "Approved plan not found (it may have expired). Please re-issue the command.",
                )
            return self._execute_plan(goal, plan, plan_id)

        # ---- Phase 1: build + pin + request approval ----
        if not goal:
            return result_failed(Intent.RUN_TOOL_TASK, "What should the tool task accomplish?")
        try:
            plan = build_search_open_summarize_plan(goal)
        except ForbiddenGoalError as exc:
            audit.record_blocked(goal, str(exc), intent="run_tool_task")
            return result_blocked(Intent.RUN_TOOL_TASK, str(exc))

        cid = confirmation.create_confirmation(
            "run_tool_task",
            {"raw_text": request.raw_text, "params": dict(request.params)},
        )
        pending.pin_plan(cid, plan)
        body = (
            f"{plan.format()}\n\n{_SAFETY_BANNER}\n"
            f"Reply yes/confirm to run this exact plan, or no/cancel to abort (id: {cid})."
        )
        return result_confirmation_required(Intent.RUN_TOOL_TASK, body, cid)

    def _execute_plan(self, goal: str, plan, plan_id: str) -> CommandResult:
        from tooluse import audit, pending
        from tooluse.contracts import RunStatus
        from tooluse.executor import ToolUseExecutor, approve_all

        provider = _make_provider()
        started = time.perf_counter()
        run = ToolUseExecutor(provider, approver=approve_all).run(plan)
        duration_ms = int((time.perf_counter() - started) * 1000)

        pending.set_last_run(run)
        pending.discard_plan(plan_id)
        audit.record_tool_run(
            goal=goal, intent="run_tool_task", confirmation_id=plan_id,
            approved=True, run=run, plan_hash=_plan_hash(plan), duration_ms=duration_ms,
        )

        body = run.format()
        if run.status == RunStatus.SUCCESS:
            if _run_has_untrusted_provider(run):
                return result_blocked(
                    Intent.RUN_TOOL_TASK,
                    f"{body}\n\nUntrusted browser provider label observed — success refused.",
                )
            return result_success(Intent.RUN_TOOL_TASK, body, data={"final_status": run.status.value})
        if run.status == RunStatus.BLOCKED_UNAVAILABLE:
            return result_blocked(
                Intent.RUN_TOOL_TASK,
                f"{body}\n\nNo real browser provider available — nothing was executed.",
            )
        return result_failed(Intent.RUN_TOOL_TASK, body, error=f"tool run {run.status.value}")


class ShowLastToolRunAction(BaseAction):
    """Read-only display of the most recent tool run."""

    intent = Intent.SHOW_LAST_TOOL_RUN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from tooluse import pending

        run = pending.get_last_run()
        if run is None:
            return result_success(
                Intent.SHOW_LAST_TOOL_RUN,
                "No tool run recorded yet. Try: run tool task <goal>",
                data={"read_only": True},
            )
        return result_success(Intent.SHOW_LAST_TOOL_RUN, run.format(), data={"read_only": True})
