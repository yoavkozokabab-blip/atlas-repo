"""Execute predefined workflows via router / handle_text_command."""

from __future__ import annotations

from collections.abc import Callable

from config import CONFIRMATION_REQUIRED_INTENTS
from core.types import ActionStatus, CommandResult, Intent
from workflows.models import WorkflowDefinition, WorkflowRunResult, WorkflowStepResult
from workflows.registry import WorkflowRegistryError, get_workflow


class WorkflowRunner:
    """
    Run fixed step sequences. Each step uses the same pipeline as console commands.
    """

    def __init__(
        self,
        execute_command: Callable[[str], CommandResult],
    ) -> None:
        self._execute = execute_command

    def run(self, workflow_name: str) -> WorkflowRunResult:
        wf = get_workflow(workflow_name)
        if wf is None:
            return WorkflowRunResult(
                workflow_name=workflow_name,
                status="unknown_workflow",
                combined_summary=f"Unknown workflow '{workflow_name}'. Run list_workflows.",
                suggested_next_steps=["Run: list workflows"],
            )

        step_results: list[WorkflowStepResult] = []
        failed_steps: list[int] = []
        lines: list[str] = [f"Workflow '{wf.name}' ({wf.title}):"]

        for index, step in enumerate(wf.steps):
            try:
                from ui.overlay_app import notify_overlay_workflow
                from ui.overlay_presence import format_workflow_hint

                notify_overlay_workflow(
                    format_workflow_hint(
                        status="running",
                        workflow_name=wf.name,
                        step_index=index,
                        step_total=len(wf.steps),
                        step_intent=step.intent,
                    )
                )
            except Exception:
                pass
            try:
                result = self._execute(step.command_text)
            except Exception as exc:
                result = CommandResult(
                    intent=Intent(step.intent),
                    status=ActionStatus.FAILED,
                    summary=f"Step raised an error: {exc}",
                    error=str(exc),
                )

            step_result = WorkflowStepResult.from_command_result(index, step, result)
            step_results.append(step_result)

            if result.status == ActionStatus.CONFIRMATION_REQUIRED:
                lines.append(
                    f"  Step {index + 1} [{step.intent}]: PAUSED — confirmation required."
                )
                try:
                    from ui.overlay_app import (
                        notify_overlay_awaiting_confirmation,
                        notify_overlay_workflow,
                    )
                    from ui.overlay_presence import format_workflow_hint

                    notify_overlay_workflow(
                        format_workflow_hint(
                            status="paused",
                            workflow_name=wf.name,
                            step_index=index,
                            step_total=len(wf.steps),
                            step_intent=step.intent,
                            paused=True,
                        )
                    )
                    notify_overlay_awaiting_confirmation(intent=step.intent)
                except Exception:
                    pass
                return WorkflowRunResult(
                    workflow_name=wf.name,
                    status="paused_confirmation",
                    step_results=step_results,
                    failed_steps=failed_steps,
                    combined_summary="\n".join(lines),
                    suggested_next_steps=[
                        "Reply yes/confirm/כן to confirm the pending step, then re-run the workflow if needed.",
                        "Reply no/cancel/לא to cancel.",
                    ],
                    paused_at_step=index,
                    confirmation_id=result.confirmation_id,
                )

            ok = result.status == ActionStatus.SUCCESS
            if not ok:
                failed_steps.append(index)
            marker = "OK" if ok else result.status.value.upper()
            lines.append(f"  Step {index + 1} [{step.intent}]: {marker} — {result.summary[:120]}")

        status = "completed"
        if failed_steps and len(failed_steps) < len(wf.steps):
            status = "completed_with_failures"
        elif failed_steps and len(failed_steps) == len(wf.steps):
            status = "failed"

        suggestions = _suggest_next_steps(wf, step_results, failed_steps)
        lines.append("")
        lines.append(f"Finished: {len(wf.steps) - len(failed_steps)}/{len(wf.steps)} steps succeeded.")
        if failed_steps:
            lines.append(f"Failed step indexes: {failed_steps}")

        return WorkflowRunResult(
            workflow_name=wf.name,
            status=status,
            step_results=step_results,
            failed_steps=failed_steps,
            combined_summary="\n".join(lines),
            suggested_next_steps=suggestions,
        )


def _suggest_next_steps(
    wf: WorkflowDefinition,
    results: list[WorkflowStepResult],
    failed: list[int],
) -> list[str]:
    steps: list[str] = []
    if failed:
        for idx in failed[:3]:
            if idx < len(wf.steps):
                steps.append(f"Re-run: {wf.steps[idx].command_text}")
    if wf.name == "trading_health_check":
        steps.append("Run: suggest next steps")
    elif wf.name == "screen_error_check":
        steps.append("Run: read screen text")
    steps.append("Run: list workflows")
    return steps[:6]


def run_workflow_via_router(workflow_name: str, router) -> WorkflowRunResult:
    """Convenience: build runner from CommandRouter.route."""
    runner = WorkflowRunner(lambda text: router.route(text, input_mode="text"))
    return runner.run(workflow_name)


def run_workflow_via_app(workflow_name: str, app) -> WorkflowRunResult:
    """Convenience: build runner from JarvisApp.handle_text_command."""
    runner = WorkflowRunner(
        lambda text: app.handle_text_command(text, input_mode="text", print_result=False)
    )
    return runner.run(workflow_name)
