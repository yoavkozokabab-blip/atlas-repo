"""Autonomous Agent Stack v1 — pinned plan/task store (in-process, no secrets)."""

from __future__ import annotations

import threading

from autonomy.planner import AutonomousPlan
from autonomy.task import AutonomousTask

_lock = threading.Lock()
_pinned: dict[str, tuple[AutonomousTask, AutonomousPlan]] = {}
_last_task: AutonomousTask | None = None


def pin(plan_id: str, task: AutonomousTask, plan: AutonomousPlan) -> None:
    with _lock:
        _pinned[plan_id] = (task, plan)


def get_pinned(plan_id: str) -> tuple[AutonomousTask, AutonomousPlan] | None:
    with _lock:
        return _pinned.get(plan_id)


def discard(plan_id: str) -> None:
    with _lock:
        _pinned.pop(plan_id, None)


def set_last_task(task: AutonomousTask) -> None:
    global _last_task
    with _lock:
        _last_task = task


def get_last_task() -> AutonomousTask | None:
    with _lock:
        return _last_task


def reset_for_tests() -> None:
    global _last_task
    with _lock:
        _pinned.clear()
        _last_task = None
