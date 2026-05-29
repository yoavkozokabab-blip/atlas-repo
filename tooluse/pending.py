"""Phase 72 — pinned-plan + last-run store (in-process, not persisted).

When a user issues `run tool task <goal>`, the action builds a dry-run plan,
**pins** it here keyed by the confirmation id, and shows it for approval.  On
"yes", the action loads the pinned plan by that id and executes *exactly* it —
guaranteeing "what was previewed is what runs".

This store holds no secrets and is intentionally process-local (cleared on
restart).
"""

from __future__ import annotations

import threading

from tooluse.contracts import ActionPlan, TaskRun

_lock = threading.Lock()
_pinned: dict[str, ActionPlan] = {}
_last_run: TaskRun | None = None


def pin_plan(plan_id: str, plan: ActionPlan) -> None:
    with _lock:
        _pinned[plan_id] = plan


def get_pinned_plan(plan_id: str) -> ActionPlan | None:
    with _lock:
        return _pinned.get(plan_id)


def discard_plan(plan_id: str) -> None:
    with _lock:
        _pinned.pop(plan_id, None)


def set_last_run(run: TaskRun) -> None:
    global _last_run
    with _lock:
        _last_run = run


def get_last_run() -> TaskRun | None:
    with _lock:
        return _last_run


def reset_for_tests() -> None:
    global _last_run
    with _lock:
        _pinned.clear()
        _last_run = None
