"""Active task session store (single supervised task at a time)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from task_agent.models import TaskSession, TaskStatus
from task_agent.planner import create_plan_from_objective


_active: TaskSession | None = None


def start_task(objective: str) -> TaskSession:
    global _active
    task_id = datetime.now(timezone.utc).strftime("task_%Y%m%d_%H%M%S")
    plan = create_plan_from_objective(objective)
    _active = TaskSession(
        task_id=task_id,
        plan=plan,
        status=TaskStatus.AWAITING_PLAN_APPROVAL,
        started_at=time.monotonic(),
    )
    return _active


def get_active_task() -> TaskSession | None:
    return _active


def stop_task() -> TaskSession | None:
    if _active is None:
        return None
    _active.stop_requested = True
    _active.status = TaskStatus.STOPPED
    return _active


def reset_task_store() -> None:
    global _active
    _active = None
