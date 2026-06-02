"""Autonomous Agent Stack v1 — structured task model."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    CREATED = "created"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"                 # some sources succeeded, goal partially met
    FAILED = "failed"
    BLOCKED_UNAVAILABLE = "blocked_unavailable"   # no real provider — never success
    BLOCKED_FORBIDDEN = "blocked_forbidden"
    EXHAUSTED = "exhausted"             # limits/recovery exhausted honestly


@dataclass
class StepResult:
    index: int
    capability: str
    status: str                         # "success" | "failed" | "skipped" | "recovered"
    detail: str = ""
    verification_ok: bool | None = None
    verification_reason: str = ""
    recovery_attempts: int = 0
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "capability": self.capability,
            "status": self.status,
            "detail": self.detail[:300],
            "verification_ok": self.verification_ok,
            "verification_reason": self.verification_reason[:200],
            "recovery_attempts": self.recovery_attempts,
            "url": self.url,
        }


def _now() -> float:
    return time.time()


@dataclass
class AutonomousTask:
    user_goal: str
    normalized_goal: str = ""
    safety_class: str = ""
    allowed_capabilities: list[str] = field(default_factory=list)
    forbidden_capabilities_detected: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.CREATED
    task_id: str = field(default_factory=lambda: f"auto_{uuid.uuid4().hex[:12]}")
    created_at: float = field(default_factory=_now)
    started_at: float | None = None
    completed_at: float | None = None
    plan_id: str = ""
    approved_plan_hash: str = ""
    current_step: int = 0
    step_results: list[StepResult] = field(default_factory=list)
    final_report: str = ""
    confidence: float = 0.0
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_goal": self.user_goal,
            "normalized_goal": self.normalized_goal,
            "safety_class": self.safety_class,
            "allowed_capabilities": list(self.allowed_capabilities),
            "forbidden_capabilities_detected": list(self.forbidden_capabilities_detected),
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "plan_id": self.plan_id,
            "approved_plan_hash": self.approved_plan_hash,
            "current_step": self.current_step,
            "step_results": [r.to_dict() for r in self.step_results],
            "final_report": self.final_report,
            "confidence": round(self.confidence, 3),
            "failure_reason": self.failure_reason,
        }
