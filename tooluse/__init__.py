"""Phase 71 — Real Tool-Use Foundation.

A bounded, production-grade observe → plan → approve → act → verify → recover
loop for safe browser tool use.  Read-only this phase: no payments, orders,
bookings, submits, logins, downloads, deletes, or sends — and no mock success.
"""

from __future__ import annotations

from tooluse.contracts import (
    ActionPlan,
    ForbiddenGoalError,
    Observation,
    PlanStep,
    RiskLevel,
    RunStatus,
    StepKind,
    StepResult,
    StepStatus,
    TaskRun,
    VerificationResult,
)
from tooluse.executor import ToolUseExecutor, approve_all, console_approver, deny_all
from tooluse.planner import build_search_open_summarize_plan
from tooluse.provider import PlaywrightBrowserProvider, ToolProvider
from tooluse.verifier import build_summary, verify_step

__all__ = [
    "ActionPlan",
    "ForbiddenGoalError",
    "Observation",
    "PlanStep",
    "RiskLevel",
    "RunStatus",
    "StepKind",
    "StepResult",
    "StepStatus",
    "TaskRun",
    "VerificationResult",
    "ToolUseExecutor",
    "approve_all",
    "console_approver",
    "deny_all",
    "build_search_open_summarize_plan",
    "PlaywrightBrowserProvider",
    "ToolProvider",
    "build_summary",
    "verify_step",
]
