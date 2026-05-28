"""Phase 25 — safe long task queue."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import DATA_DIR, TASK_QUEUE_MAX_RUNTIME_SECONDS

QUEUE_PATH = DATA_DIR / "task_queue.json"


@dataclass
class QueuedTask:
    task_id: str
    objective: str
    status: str = "queued"  # queued | running | paused | done | stopped
    progress_pct: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    max_runtime_seconds: int = TASK_QUEUE_MAX_RUNTIME_SECONDS


@dataclass
class TaskQueueState:
    paused: bool = False
    running_task_id: str | None = None
    tasks: list[QueuedTask] = field(default_factory=list)


def _load() -> TaskQueueState:
    if not QUEUE_PATH.is_file():
        return TaskQueueState()
    try:
        raw = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        tasks = [QueuedTask(**t) for t in raw.get("tasks", [])]
        return TaskQueueState(
            paused=bool(raw.get("paused", False)),
            running_task_id=raw.get("running_task_id"),
            tasks=tasks,
        )
    except (json.JSONDecodeError, TypeError):
        return TaskQueueState()


def _save(state: TaskQueueState) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "paused": state.paused,
        "running_task_id": state.running_task_id,
        "tasks": [asdict(t) for t in state.tasks],
    }
    QUEUE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def reset_queue_store() -> None:
    if QUEUE_PATH.is_file():
        try:
            QUEUE_PATH.unlink()
        except OSError:
            try:
                _save(TaskQueueState())
            except OSError:
                pass


def enqueue(objective: str) -> QueuedTask:
    state = _load()
    task = QueuedTask(task_id=f"q_{uuid.uuid4().hex[:8]}", objective=objective.strip())
    state.tasks.append(task)
    _save(state)
    return task


def format_queue() -> str:
    state = _load()
    lines = [
        f"Queue paused: {state.paused}",
        f"Running: {state.running_task_id or '(none)'}",
        f"Max runtime (s): {TASK_QUEUE_MAX_RUNTIME_SECONDS}",
        "",
        "Tasks:",
    ]
    if not state.tasks:
        lines.append("  (empty)")
    for t in state.tasks:
        elapsed = ""
        if t.started_at and t.status == "running":
            elapsed = f" elapsed={int(time.time() - t.started_at)}s"
        lines.append(
            f"  [{t.status}] {t.task_id} {t.progress_pct:.0f}% — {t.objective[:60]}{elapsed}"
        )
    return "\n".join(lines)


def pause_queue() -> str:
    state = _load()
    state.paused = True
    if state.running_task_id:
        for t in state.tasks:
            if t.task_id == state.running_task_id:
                t.status = "paused"
    _save(state)
    return "Task queue paused."


def resume_queue() -> str:
    state = _load()
    state.paused = False
    for t in state.tasks:
        if t.status == "paused":
            t.status = "queued"
    _save(state)
    return "Task queue resumed (queued tasks can be started via supervised task agent)."


def tick_running() -> None:
    """Update progress for running task (called from tests/executor hooks)."""
    state = _load()
    if not state.running_task_id:
        return
    for t in state.tasks:
        if t.task_id != state.running_task_id:
            continue
        if t.started_at and time.time() - t.started_at > t.max_runtime_seconds:
            t.status = "stopped"
            state.running_task_id = None
        else:
            t.progress_pct = min(99.0, t.progress_pct + 5.0)
    _save(state)
