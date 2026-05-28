"""Workflow data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.types import ActionStatus, CommandResult


@dataclass
class WorkflowStep:
    """One predefined step (intent + phrase routed through classifier)."""

    intent: str
    command_text: str
    description: str = ""


@dataclass
class WorkflowDefinition:
    """Predefined multi-step workflow (code-only, no LLM planning)."""

    name: str
    title: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    read_only: bool = True
    aliases: list[str] = field(default_factory=list)


@dataclass
class WorkflowStepResult:
    step_index: int
    intent: str
    command_text: str
    status: ActionStatus
    summary: str
    error: str | None = None
    confirmation_id: str | None = None

    @classmethod
    def from_command_result(
        cls,
        index: int,
        step: WorkflowStep,
        result: CommandResult,
    ) -> "WorkflowStepResult":
        return cls(
            step_index=index,
            intent=step.intent,
            command_text=step.command_text,
            status=result.status,
            summary=result.summary,
            error=result.error,
            confirmation_id=result.confirmation_id,
        )


@dataclass
class WorkflowRunResult:
    workflow_name: str
    status: str
    step_results: list[WorkflowStepResult] = field(default_factory=list)
    failed_steps: list[int] = field(default_factory=list)
    combined_summary: str = ""
    suggested_next_steps: list[str] = field(default_factory=list)
    paused_at_step: int | None = None
    confirmation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "status": self.status,
            "combined_summary": self.combined_summary,
            "failed_steps": self.failed_steps,
            "suggested_next_steps": self.suggested_next_steps,
            "paused_at_step": self.paused_at_step,
            "confirmation_id": self.confirmation_id,
            "step_results": [
                {
                    "step_index": s.step_index,
                    "intent": s.intent,
                    "command_text": s.command_text,
                    "status": s.status.value,
                    "summary": s.summary,
                    "error": s.error,
                }
                for s in self.step_results
            ],
        }
