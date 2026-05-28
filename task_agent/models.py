"""Task agent data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from task_agent.findings import TaskFinding
    from task_agent.patch_proposals import PatchProposal


class TaskPhase(str, Enum):
    INSPECT = "inspect"
    PLAN = "plan"
    AWAIT_APPROVAL = "await_approval"
    EXECUTE = "execute"
    TEST = "test"
    REPORT = "report"
    STOPPED = "stopped"
    COMPLETE = "complete"


class StepKind(str, Enum):
    READONLY = "readonly"
    CONFIRM_REQUIRED = "confirm_required"
    BLOCKED = "blocked"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"


class TaskStatus(str, Enum):
    NO_TASK = "no_task"
    PLAN_READY = "plan_ready"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    APPROVED = "approved"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETE = "complete"


@dataclass
class TaskStep:
    step_id: str
    title: str
    kind: StepKind
    command_key: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result_summary: str = ""
    requires_separate_approval: bool = False


@dataclass
class TaskPlan:
    objective: str
    assumptions: list[str] = field(default_factory=list)
    steps: list[TaskStep] = field(default_factory=list)
    required_approvals: list[str] = field(default_factory=list)
    files_likely_needed: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def format_plan(self) -> str:
        lines = [
            f"Objective: {self.objective}",
            "",
            "Assumptions:",
        ]
        lines.extend(f"  - {a}" for a in self.assumptions) or ["  - (none)"]
        lines.append("")
        lines.append("Steps:")
        for i, step in enumerate(self.steps, start=1):
            flag = step.kind.value
            if step.requires_separate_approval:
                flag += " [needs approval]"
            lines.append(f"  {i}. [{flag}] {step.title} ({step.command_key})")
        lines.append("")
        lines.append("Required approvals:")
        lines.extend(f"  - {a}" for a in self.required_approvals) or ["  - Plan approval"]
        lines.append("")
        lines.append("Files likely needed:")
        lines.extend(f"  - {f}" for f in self.files_likely_needed) or ["  - (inferred)"]
        lines.append("")
        lines.append("Allowed commands:")
        lines.extend(f"  - {c}" for c in self.allowed_commands)
        return "\n".join(lines)


@dataclass
class TaskSession:
    task_id: str
    plan: TaskPlan
    status: TaskStatus = TaskStatus.AWAITING_PLAN_APPROVAL
    phase: TaskPhase = TaskPhase.PLAN
    plan_approved: bool = False
    approved_step_ids: set[str] = field(default_factory=set)
    current_step_index: int = 0
    steps_completed: int = 0
    stop_requested: bool = False
    report_path: str = ""
    started_at: float = 0.0
    findings: list[str] = field(default_factory=list)
    structured_findings: list["TaskFinding"] = field(default_factory=list)
    patch_proposal: "PatchProposal | None" = None
    git_diff_before: str = ""
    git_diff_after: str = ""
    patch_backup_dir: str = ""
    patch_applied: bool = False

    def pending_steps(self) -> list[TaskStep]:
        return [s for s in self.plan.steps if s.status == StepStatus.PENDING]
