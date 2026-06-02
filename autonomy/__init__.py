"""Autonomous Agent Stack v1 — bounded, read-only research agent.

Plan -> preview -> approve (pinned hash) -> execute (observe/act/verify/recover)
-> report. Read-only only: no payments/orders/bookings/logins/submits/downloads/
deletes/sends, no desktop control, and no mock success.
"""

from __future__ import annotations

from autonomy.capabilities import (
    ALLOWED_CAPABILITIES,
    FORBIDDEN_CAPABILITIES,
    Capability,
    SafetyClass,
    classify_goal,
)
from autonomy.executor import AutonomousExecutor
from autonomy.limits import RunLimits
from autonomy.planner import AutonomousPlan, ResearchStep, build_research_plan, normalize_goal
from autonomy.provider import AutonomousBrowserProvider, AutonomyProvider
from autonomy.task import AutonomousTask, StepResult, TaskStatus

__all__ = [
    "ALLOWED_CAPABILITIES", "FORBIDDEN_CAPABILITIES", "Capability", "SafetyClass",
    "classify_goal", "AutonomousExecutor", "RunLimits", "AutonomousPlan",
    "ResearchStep", "build_research_plan", "normalize_goal",
    "AutonomousBrowserProvider", "AutonomyProvider",
    "AutonomousTask", "StepResult", "TaskStatus",
]
