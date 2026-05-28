"""Workflow list / run / explain actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from actions.base import BaseAction
from core.results import result_failed, result_success

if TYPE_CHECKING:
    from brain.router import CommandRouter
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from workflows.registry import get_workflow, list_workflow_names, resolve_workflow_alias
from workflows.runner import run_workflow_via_router


class ListWorkflowsAction(BaseAction):
    intent = Intent.LIST_WORKFLOWS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        names = list_workflow_names()
        lines = ["Predefined workflows (read-only steps, router path only):"]
        for name in names:
            wf = get_workflow(name)
            if wf:
                lines.append(f"  - {name}: {wf.title} — {wf.description}")
        return result_success(
            Intent.LIST_WORKFLOWS,
            "\n".join(lines),
            data={"workflows": names},
        )


class RunWorkflowAction(BaseAction):
    intent = Intent.RUN_WORKFLOW.value

    def __init__(self, router: "CommandRouter | None" = None) -> None:
        self._router = router

    def execute(self, request: CommandRequest) -> CommandResult:
        from brain.router import CommandRouter
        name = (
            request.params.get("workflow")
            or request.params.get("name")
            or ""
        ).strip().lower()
        if not name:
            alias = resolve_workflow_alias(request.raw_text)
            if alias:
                name = alias

        if not name:
            return result_failed(
                Intent.RUN_WORKFLOW,
                "Specify workflow name, e.g. run workflow trading_health_check",
            )

        router = self._router or CommandRouter()
        run_result = run_workflow_via_router(name, router)
        data = run_result.to_dict()

        if run_result.status == "unknown_workflow":
            return result_failed(
                Intent.RUN_WORKFLOW,
                run_result.combined_summary,
                data=data,
            )

        if run_result.status == "paused_confirmation":
            return CommandResult(
                intent=Intent.RUN_WORKFLOW,
                status=ActionStatus.CONFIRMATION_REQUIRED,
                summary=run_result.combined_summary,
                data=data,
                requires_confirmation=True,
                confirmation_id=run_result.confirmation_id,
                next_suggestions=run_result.suggested_next_steps,
            )

        status = (
            ActionStatus.SUCCESS
            if run_result.status in ("completed", "completed_with_failures")
            else ActionStatus.FAILED
        )
        return CommandResult(
            intent=Intent.RUN_WORKFLOW,
            status=status,
            summary=run_result.combined_summary,
            data=data,
            next_suggestions=run_result.suggested_next_steps,
        )


class ExplainWorkflowAction(BaseAction):
    intent = Intent.EXPLAIN_WORKFLOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        name = (
            request.params.get("workflow")
            or request.params.get("name")
            or ""
        ).strip().lower()
        if not name:
            if "מסחר" in request.raw_text or "trading" in request.raw_text.lower():
                name = "trading_health_check"
            else:
                alias = resolve_workflow_alias(request.raw_text)
                name = alias or ""

        wf = get_workflow(name) if name else None
        if wf is None:
            return result_failed(
                Intent.EXPLAIN_WORKFLOW,
                f"Unknown workflow '{name}'. Run list workflows.",
            )

        lines = [
            f"{wf.name} — {wf.title}",
            wf.description,
            f"Read-only: {wf.read_only}",
            "Steps:",
        ]
        for i, step in enumerate(wf.steps, 1):
            lines.append(f"  {i}. {step.intent} — {step.description or step.command_text}")
        return result_success(
            Intent.EXPLAIN_WORKFLOW,
            "\n".join(lines),
            data={
                "name": wf.name,
                "steps": [s.intent for s in wf.steps],
                "read_only": wf.read_only,
            },
        )
