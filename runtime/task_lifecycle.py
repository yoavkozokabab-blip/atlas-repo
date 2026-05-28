"""Persistent task lifecycle engine (Phase 53)."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.runtime.task_lifecycle")

TASK_RESULTS_DIR = DATA_DIR / "task_results"
TASK_LIFECYCLE_DIR = DATA_DIR / "task_lifecycle"
TASK_STATE_PATH = TASK_LIFECYCLE_DIR / "state.json"
LIFECYCLE_REPORT_DIR = PROJECT_ROOT / "reports" / "task_lifecycle"
RESULT_CACHE_LIMIT = 200
HEARTBEAT_SECONDS = 5.0


class TaskPhase(str, Enum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self in {
            TaskPhase.COMPLETED,
            TaskPhase.FAILED,
            TaskPhase.CANCELLED,
            TaskPhase.TIMED_OUT,
        }


ACTIVE_PHASES = frozenset(
    {
        TaskPhase.QUEUED,
        TaskPhase.STARTING,
        TaskPhase.RUNNING,
        TaskPhase.STREAMING,
    }
)


@dataclass
class TaskRecord:
    id: int
    command: str
    intent: str
    phase: TaskPhase = TaskPhase.QUEUED
    started_at: str = ""
    started_monotonic: float = 0.0
    last_progress_at: str = ""
    last_progress_text: str = ""
    ended_at: str = ""
    duration_seconds: float = 0.0
    result_summary: str = ""
    severity: str = "info"
    evidence: list[str] = field(default_factory=list)
    related_reports: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notification_id: int | None = None
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["phase"] = self.phase.value
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        phase_raw = str(data.get("phase", TaskPhase.QUEUED.value))
        try:
            phase = TaskPhase(phase_raw)
        except ValueError:
            phase = TaskPhase.FAILED
        return cls(
            id=int(data["id"]),
            command=str(data.get("command", "")),
            intent=str(data.get("intent", "")),
            phase=phase,
            started_at=str(data.get("started_at", "")),
            started_monotonic=float(data.get("started_monotonic", 0.0) or 0.0),
            last_progress_at=str(data.get("last_progress_at", "")),
            last_progress_text=str(data.get("last_progress_text", "")),
            ended_at=str(data.get("ended_at", "")),
            duration_seconds=float(data.get("duration_seconds", 0.0) or 0.0),
            result_summary=str(data.get("result_summary", "")),
            severity=str(data.get("severity", "info")),
            evidence=[str(x) for x in data.get("evidence", [])][:20],
            related_reports=[str(x) for x in data.get("related_reports", [])][:20],
            errors=[str(x) for x in data.get("errors", [])][:10],
            notification_id=data.get("notification_id"),
            cancel_requested=bool(data.get("cancel_requested")),
        )


_current_task_id: threading.local = threading.local()
_manager: TaskLifecycleManager | None = None
_manager_lock = threading.Lock()


class TaskLifecycleManager:
    """Authoritative task state with persistence and live elapsed tracking."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[int, TaskRecord] = {}
        self._result_index: dict[int, Path] = {}
        self._next_id = 1
        self._last_completed_id: int | None = None
        self._heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            name="jarvis-task-lifecycle-heartbeat",
            daemon=True,
        )
        self._load_state()
        self._recover_orphans()
        self._heartbeat.start()

    def create_task(self, command: str, intent: str) -> TaskRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            task_id = self._next_id
            self._next_id += 1
            task = TaskRecord(
                id=task_id,
                command=command,
                intent=intent,
                phase=TaskPhase.QUEUED,
                started_at=now,
                started_monotonic=time.monotonic(),
                last_progress_at=now,
            )
            self._tasks[task_id] = task
            self._persist_state()
        return task

    def set_phase(self, task_id: int, phase: TaskPhase) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.phase = phase
            if phase in ACTIVE_PHASES and not task.started_monotonic:
                task.started_monotonic = time.monotonic()
            self._persist_state()

    def touch_progress(self, task_id: int, message: str) -> None:
        msg = (message or "").strip()
        if not msg:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.last_progress_at = now
            task.last_progress_text = msg[:200]
            if task.phase in {TaskPhase.RUNNING, TaskPhase.STARTING}:
                task.phase = TaskPhase.STREAMING

    def record_result_line(self, task_id: int, message: str, *, severity: str = "info") -> None:
        msg = (message or "").strip()
        if not msg:
            return
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if msg not in task.evidence:
                task.evidence.append(msg[:300])
            if severity in {"warning", "error", "critical"}:
                task.severity = severity

    def attach_notification(self, task_id: int, notification_id: int) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is not None:
                task.notification_id = notification_id

    def finalize(
        self,
        task_id: int,
        *,
        phase: TaskPhase,
        summary: str = "",
        severity: str = "info",
        errors: list[str] | None = None,
        related_reports: list[str] | None = None,
        notification_id: int | None = None,
    ) -> TaskRecord | None:
        ended = datetime.now(timezone.utc).isoformat()
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            started_mono = task.started_monotonic or time.monotonic()
            task.phase = phase
            task.ended_at = ended
            task.duration_seconds = round(max(0.0, time.monotonic() - started_mono), 2)
            task.result_summary = (summary or "")[:800]
            task.severity = severity
            if errors:
                task.errors.extend(errors[:10])
            if related_reports:
                for report in related_reports:
                    if report and report not in task.related_reports:
                        task.related_reports.append(report)
            if notification_id is not None:
                task.notification_id = notification_id
            if phase == TaskPhase.COMPLETED:
                self._last_completed_id = task_id
            self._persist_result(task)
            self._persist_state()
            self._write_lifecycle_report(task)
            try:
                from assistant.continuity_engine import record_task_completion

                record_task_completion(task)
            except Exception:
                pass
            return replace(task)

    def cancel_requested(self, task_id: int) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is not None:
                task.cancel_requested = True
                self._persist_state()

    def get(self, task_id: int) -> TaskRecord | None:
        with self._lock:
            live = self._tasks.get(task_id)
            if live is not None:
                return TaskRecord(**asdict(live))
        return self._load_result(task_id)

    def live_elapsed(self, task: TaskRecord) -> float:
        if task.phase.is_terminal:
            return task.duration_seconds
        if task.started_monotonic:
            return max(0.0, time.monotonic() - task.started_monotonic)
        return 0.0

    def list_active(self) -> list[TaskRecord]:
        with self._lock:
            items = [TaskRecord(**asdict(t)) for t in self._tasks.values() if t.phase in ACTIVE_PHASES]
        items.sort(key=lambda t: t.id)
        return items

    def list_by_phase(self, phases: set[TaskPhase]) -> list[TaskRecord]:
        results: list[TaskRecord] = []
        with self._lock:
            for task in self._tasks.values():
                if task.phase in phases:
                    results.append(TaskRecord(**asdict(task)))
        for task_id, path in self._result_index.items():
            if any(t.id == task_id for t in results):
                continue
            loaded = self._load_result_from_path(path)
            if loaded and loaded.phase in phases:
                results.append(loaded)
        results.sort(key=lambda t: t.ended_at or t.started_at, reverse=True)
        return results

    def list_recent(self, *, limit: int = 10) -> list[TaskRecord]:
        terminal = {
            TaskPhase.COMPLETED,
            TaskPhase.FAILED,
            TaskPhase.CANCELLED,
            TaskPhase.TIMED_OUT,
        }
        items = self.list_by_phase(terminal)
        return items[:limit]

    def get_last_completed(self) -> TaskRecord | None:
        with self._lock:
            if self._last_completed_id is not None:
                task = self._tasks.get(self._last_completed_id)
                if task and task.phase == TaskPhase.COMPLETED:
                    return TaskRecord(**asdict(task))
        completed = self.list_by_phase({TaskPhase.COMPLETED})
        return completed[0] if completed else None

    def explain_last_result(self) -> str:
        last = self.get_last_completed()
        if last is None:
            recent = self.list_recent(limit=1)
            if not recent:
                return "No recent task results."
            last = recent[0]
        return self.format_detail(last)

    def reopen_result(self, task_id: int) -> str:
        task = self.get(task_id)
        if task is None:
            return f"No stored result for task {task_id}."
        if task.phase not in {
            TaskPhase.COMPLETED,
            TaskPhase.FAILED,
            TaskPhase.CANCELLED,
            TaskPhase.TIMED_OUT,
        }:
            return f"Task {task_id} is still {task.phase.value}."
        return self.format_detail(task)

    def format_list(self, tasks: list[TaskRecord], *, title: str) -> str:
        if not tasks:
            return f"{title}: none."
        lines = [f"{title} ({len(tasks)}):"]
        for task in tasks:
            elapsed = self.live_elapsed(task)
            progress = f" — {task.last_progress_text[:60]}" if task.last_progress_text else ""
            lines.append(
                f"  [{task.id}] {task.phase.value} {task.command[:55]} "
                f"({elapsed:.1f}s){progress}"
            )
            if task.result_summary and task.phase.is_terminal:
                lines.append(f"       {task.result_summary[:120]}")
        return "\n".join(lines)

    def format_detail(self, task: TaskRecord) -> str:
        elapsed = self.live_elapsed(task)
        lines = [
            f"Task {task.id}: {task.command}",
            f"  phase: {task.phase.value}",
            f"  intent: {task.intent}",
            f"  severity: {task.severity}",
            f"  elapsed: {elapsed:.1f}s",
            f"  started: {task.started_at}",
        ]
        if task.ended_at:
            lines.append(f"  ended: {task.ended_at}")
        if task.last_progress_text:
            lines.append(f"  last progress: {task.last_progress_text}")
        if task.result_summary:
            lines.append(f"  summary: {task.result_summary[:500]}")
        if task.evidence:
            lines.append("  evidence:")
            for item in task.evidence[:8]:
                lines.append(f"    - {item[:160]}")
        if task.errors:
            lines.append(f"  error: {task.errors[0][:200]}")
        if task.related_reports:
            lines.append("  related reports:")
            for report in task.related_reports[:6]:
                lines.append(f"    - {report}")
        if task.notification_id is not None:
            lines.append(f"  notification id: {task.notification_id}")
        return "\n".join(lines)

    def _heartbeat_loop(self) -> None:
        while True:
            try:
                self._persist_state()
            except Exception as exc:
                logger.debug("Task lifecycle heartbeat: %s", exc)
            time.sleep(HEARTBEAT_SECONDS)

    def _load_state(self) -> None:
        TASK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        TASK_LIFECYCLE_DIR.mkdir(parents=True, exist_ok=True)

        def _validate(data: Any) -> dict[str, Any] | None:
            if not isinstance(data, dict):
                return None
            return data

        state = load_json(TASK_STATE_PATH, default={"next_id": 1, "tasks": {}, "last_completed_id": None}, validator=_validate)
        self._next_id = int(state.get("next_id", 1) or 1)
        self._last_completed_id = state.get("last_completed_id")
        tasks_raw = state.get("tasks", {})
        if isinstance(tasks_raw, dict):
            for key, payload in tasks_raw.items():
                try:
                    task = TaskRecord.from_dict(payload if isinstance(payload, dict) else {})
                    self._tasks[int(key)] = task
                except (TypeError, ValueError, KeyError):
                    continue
        for path in TASK_RESULTS_DIR.glob("task_*.json"):
            try:
                task_id = int(path.stem.split("_", 1)[1])
            except (IndexError, ValueError):
                continue
            self._result_index[task_id] = path
            if task_id not in self._tasks:
                loaded = self._load_result_from_path(path)
                if loaded:
                    self._tasks[task_id] = loaded
        if self._next_id <= max(self._tasks.keys(), default=0):
            self._next_id = max(self._tasks.keys(), default=0) + 1

    def _recover_orphans(self) -> None:
        with self._lock:
            for task in self._tasks.values():
                if task.phase in ACTIVE_PHASES:
                    task.phase = TaskPhase.FAILED
                    task.errors.append("Recovered orphan task after restart")
                    task.result_summary = task.result_summary or "Task interrupted by restart"
                    task.ended_at = datetime.now(timezone.utc).isoformat()
                    if task.started_monotonic:
                        task.duration_seconds = round(
                            max(0.0, time.monotonic() - task.started_monotonic),
                            2,
                        )
                    self._persist_result(task)
            self._persist_state()

    def _persist_state(self) -> None:
        with self._lock:
            payload = {
                "next_id": self._next_id,
                "last_completed_id": self._last_completed_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "tasks": {
                    str(task.id): task.to_dict()
                    for task in self._tasks.values()
                    if not task.phase.is_terminal or task.id in self._result_index
                },
            }
        atomic_write_json(TASK_STATE_PATH, payload)

    def _persist_result(self, task: TaskRecord) -> None:
        path = TASK_RESULTS_DIR / f"task_{task.id}.json"
        atomic_write_json(path, task.to_dict())
        self._result_index[task.id] = path
        self._trim_results()

    def _load_result(self, task_id: int) -> TaskRecord | None:
        path = self._result_index.get(task_id)
        if path is None:
            path = TASK_RESULTS_DIR / f"task_{task_id}.json"
        return self._load_result_from_path(path)

    def _load_result_from_path(self, path: Path) -> TaskRecord | None:
        if not path.is_file():
            return None

        def _validate(data: Any) -> dict[str, Any] | None:
            return data if isinstance(data, dict) else None

        data = load_json(path, default={}, validator=_validate)
        if not data:
            return None
        try:
            return TaskRecord.from_dict(data)
        except (TypeError, ValueError, KeyError):
            return None

    def _trim_results(self) -> None:
        if len(self._result_index) <= RESULT_CACHE_LIMIT:
            return
        paths = sorted(self._result_index.values(), key=lambda p: p.stat().st_mtime)
        for path in paths[: len(paths) - RESULT_CACHE_LIMIT]:
            try:
                task_id = int(path.stem.split("_", 1)[1])
            except (IndexError, ValueError):
                task_id = None
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            if task_id is not None:
                self._result_index.pop(task_id, None)

    def _write_lifecycle_report(self, task: TaskRecord) -> None:
        try:
            LIFECYCLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = LIFECYCLE_REPORT_DIR / f"{ts}_task_{task.id}.json"
            path.write_text(json.dumps(task.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        except OSError as exc:
            logger.debug("Lifecycle report write failed: %s", exc)


def get_task_lifecycle() -> TaskLifecycleManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = TaskLifecycleManager()
        return _manager


def set_current_task_id(task_id: int | None) -> None:
    _current_task_id.value = task_id


def get_current_task_id() -> int | None:
    return getattr(_current_task_id, "value", None)


def touch_task_progress(message: str, *, task_id: int | None = None) -> None:
    tid = task_id if task_id is not None else get_current_task_id()
    if tid is None:
        return
    get_task_lifecycle().touch_progress(tid, message)


def reset_task_lifecycle_for_tests() -> None:
    global _manager
    with _manager_lock:
        _manager = None
