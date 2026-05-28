"""Background task engine for async investigations (Phase 52/53)."""

from __future__ import annotations

import os
import threading
import time
import weakref
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from config import PROJECT_ROOT
from core.logger import setup_logger
from core.types import Intent
from runtime.task_lifecycle import (
    TaskPhase,
    TaskRecord,
    get_task_lifecycle,
    set_current_task_id,
    touch_task_progress,
)

if TYPE_CHECKING:
    from core.app import JarvisApp
    from core.types import CommandResult

logger = setup_logger("jarvis.runtime.background_tasks")

TASK_REPORT_DIR = PROJECT_ROOT / "reports" / "runtime_tasks"

HEAVY_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.RECONSTRUCT_EXECUTION_FLOW,
        Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
        Intent.REPLAY_AFTER_PATCH,
        Intent.SHOW_TRADING_OPERATIONS_DASHBOARD,
        Intent.SUMMARIZE_TRADING_HEALTH,
    }
)

TASK_CONTROL_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.SHOW_RUNNING_TASKS,
        Intent.CANCEL_TASK,
        Intent.SHOW_COMPLETED_TASKS,
        Intent.SHOW_FAILED_TASKS,
        Intent.RERUN_LAST_BACKGROUND_TASK,
        Intent.SHOW_RECENT_RESULTS,
        Intent.SHOW_NOTIFICATIONS,
        Intent.CLEAR_NOTIFICATIONS,
        Intent.EXPLAIN_LAST_RESULT,
        Intent.REOPEN_TASK_RESULT,
        Intent.ARCHIVE_NOTIFICATION,
        Intent.EXPLAIN_NOTIFICATION,
        Intent.CONTINUE_PREVIOUS_SESSION,
        Intent.SUMMARIZE_UNRESOLVED_ISSUES,
        Intent.RESUME_LATEST_INVESTIGATION,
        Intent.WHAT_CHANGED_SINCE_LAST_SESSION,
        Intent.SUMMARIZE_SYSTEM_INTELLIGENCE,
        Intent.SUMMARIZE_UNRESOLVED_BLOCKERS,
        Intent.EXPLAIN_CURRENT_OPERATIONAL_STATE,
        Intent.RECOMMEND_NEXT_ACTION,
        Intent.WHAT_SHOULD_WE_INVESTIGATE_NEXT,
        Intent.SHOW_INVESTIGATION_SCHEDULE,
        Intent.RUN_INVESTIGATION_CYCLE,
        Intent.PAUSE_INVESTIGATION_LOOP,
        Intent.RESUME_INVESTIGATION_LOOP,
        Intent.RUN_NIGHTLY_INVESTIGATION_NOW,
        Intent.SHOW_BLOCKER_TRENDS,
        Intent.COMPARE_BLOCKER_TRENDS,
        Intent.EXPLAIN_DOMINANT_BLOCKER,
        Intent.SHOW_BLOCKER_HISTORY,
        Intent.CLUSTER_REPLAY_DIVERGENCES,
        Intent.SHOW_DIVERGENCE_CLUSTERS,
        Intent.EXPLAIN_LARGEST_DIVERGENCE_CLUSTER,
        Intent.SHOW_ACTIVE_HYPOTHESES,
        Intent.VERIFY_ACTIVE_HYPOTHESES,
        Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS,
        Intent.COMPARE_HYPOTHESIS_HISTORY,
        Intent.SHOW_INTELLIGENCE_TIMELINE,
        Intent.EXPLAIN_RECENT_ANOMALIES,
        Intent.COMPARE_TODAY_VS_YESTERDAY_INTELLIGENCE,
        Intent.SUMMARIZE_AUTONOMOUS_FINDINGS,
        Intent.SUMMARIZE_OPERATIONAL_ANOMALIES,
        Intent.EXPLAIN_CURRENT_TRADING_RISK,
        Intent.SHOW_VERIFICATION_PLANS,
        Intent.EXPLAIN_VERIFICATION_PLAN,
        Intent.RUN_VERIFICATION_PLAN,
        Intent.VERIFY_ROOT_CAUSES,
        Intent.SHOW_CONFIDENCE_EVOLUTION,
        Intent.EXPLAIN_CONFIDENCE_CHANGES,
        Intent.COMPARE_ROOT_CAUSE_CONFIDENCE,
        Intent.SHOW_CONTRADICTORY_EVIDENCE,
        Intent.EXPLAIN_CONTRADICTION,
        Intent.RESOLVE_CONTRADICTION,
        Intent.SUGGEST_EXPERIMENTS,
        Intent.EXPLAIN_EXPERIMENT_IMPACT,
        Intent.RUN_SAFE_EXPERIMENT_SIMULATION,
        Intent.SHOW_ROOT_CAUSE_GRAPH,
        Intent.EXPLAIN_ROOT_CAUSE_GRAPH,
        Intent.TRACE_CAUSAL_CHAIN,
        Intent.SUMMARIZE_ROOT_CAUSES,
        Intent.EXPLAIN_DOMINANT_ROOT_CAUSE,
        Intent.EXPLAIN_OPERATIONAL_FAILURES,
        Intent.SUMMARIZE_VERIFIED_FINDINGS,
        Intent.EXPLAIN_WHY_TRADES_ARE_BLOCKED,
        Intent.COMPARE_OPERATIONAL_PERIODS,
        Intent.COMPARE_BEFORE_AFTER_CLEANUP,
        Intent.COMPARE_INVESTIGATION_PERIODS,
    }
)

MAX_CONCURRENT_TASKS = 3
MAX_QUEUED_TASKS = 20
TASK_TIMEOUT_SECONDS = 600.0
STUCK_TASK_SECONDS = 120.0


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class BackgroundTask:
    """Compatibility view for Phase 52 callers."""

    id: int
    command: str
    intent: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: str = ""
    ended_at: str = ""
    duration_seconds: float = 0.0
    result_summary: str = ""
    errors: list[str] = field(default_factory=list)
    related_reports: list[str] = field(default_factory=list)
    cancel_requested: bool = False

    @classmethod
    def from_record(cls, record: TaskRecord, *, lifecycle: Any) -> BackgroundTask:
        status_map = {
            TaskPhase.QUEUED: TaskStatus.PENDING,
            TaskPhase.STARTING: TaskStatus.PENDING,
            TaskPhase.RUNNING: TaskStatus.RUNNING,
            TaskPhase.STREAMING: TaskStatus.RUNNING,
            TaskPhase.COMPLETED: TaskStatus.COMPLETED,
            TaskPhase.FAILED: TaskStatus.FAILED,
            TaskPhase.CANCELLED: TaskStatus.CANCELLED,
            TaskPhase.TIMED_OUT: TaskStatus.TIMEOUT,
        }
        elapsed = lifecycle.live_elapsed(record)
        return cls(
            id=record.id,
            command=record.command,
            intent=record.intent,
            status=status_map.get(record.phase, TaskStatus.FAILED),
            started_at=record.started_at,
            ended_at=record.ended_at,
            duration_seconds=elapsed if not record.phase.is_terminal else record.duration_seconds,
            result_summary=record.result_summary,
            errors=list(record.errors),
            related_reports=list(record.related_reports),
            cancel_requested=record.cancel_requested,
        )


_engine: BackgroundTaskEngine | None = None
_engine_lock = threading.Lock()


class BackgroundTaskEngine:
    """Runs heavy commands off the console thread with visible progress."""

    def __init__(self) -> None:
        self._lifecycle = get_task_lifecycle()
        self._lock = threading.RLock()
        self._futures: dict[int, Future[None]] = {}
        self._cancel_flags: dict[int, threading.Event] = {}
        self._app_ref: weakref.ref | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_TASKS,
            thread_name_prefix="jarvis-bg-task",
        )
        self._monitor = threading.Thread(
            target=self._monitor_loop,
            name="jarvis-bg-task-monitor",
            daemon=True,
        )
        self._monitor.start()
        try:
            from assistant.continuity_engine import note_session_start

            note_session_start()
        except Exception as exc:
            logger.debug("Continuity session start skipped: %s", exc)
        if not os.environ.get("JARVIS_SKIP_INVESTIGATION_SCHEDULER"):
            try:
                from assistant.investigation_scheduler import start_investigation_scheduler

                start_investigation_scheduler()
            except Exception as exc:
                logger.debug("Investigation scheduler start skipped: %s", exc)
        try:
            from assistant.proactive_monitor import start_proactive_monitor

            start_proactive_monitor()
        except Exception as exc:
            logger.debug("Proactive monitor start skipped: %s", exc)
        try:
            from assistant.proactive_assistant import start_proactive_assistant

            start_proactive_assistant()
        except Exception as exc:
            logger.debug("Proactive assistant start skipped: %s", exc)

    def is_heavy_intent(self, intent: Intent) -> bool:
        return intent in HEAVY_INTENTS

    def should_run_async(self, intent: Intent, *, input_mode: str) -> bool:
        if intent not in HEAVY_INTENTS:
            return False
        if input_mode in {"background", "async"}:
            return False
        if intent in TASK_CONTROL_INTENTS:
            return False
        return input_mode == "console"

    def active_count(self) -> int:
        return len(self._lifecycle.list_active())

    def submit(self, app: JarvisApp, command: str, intent: Intent) -> int:
        if self.active_count() >= MAX_QUEUED_TASKS:
            raise RuntimeError(
                f"Background task queue full ({MAX_QUEUED_TASKS}). "
                "Cancel a task or wait for completion."
            )
        record = self._lifecycle.create_task(command, intent.value)
        task_id = record.id
        cancel_flag = threading.Event()
        with self._lock:
            self._cancel_flags[task_id] = cancel_flag
            self._app_ref = weakref.ref(app)
        self._lifecycle.set_phase(task_id, TaskPhase.STARTING)
        print(f"[RESULT] background task {task_id} queued: {command}", flush=True)
        future = self._executor.submit(
            self._run_task,
            app,
            task_id,
            command,
            intent,
            cancel_flag,
        )
        with self._lock:
            self._futures[task_id] = future
        return task_id

    def _run_task(
        self,
        app: JarvisApp,
        task_id: int,
        command: str,
        intent: Intent,
        cancel_flag: threading.Event,
    ) -> None:
        from runtime.result_stream import ResultStream

        set_current_task_id(task_id)
        self._lifecycle.set_phase(task_id, TaskPhase.RUNNING)
        stream = ResultStream.start(command, task_id=task_id)
        result: CommandResult | None = None
        error_text = ""
        phase = TaskPhase.FAILED
        summary = ""
        severity = "info"
        notification_id: int | None = None
        try:
            if cancel_flag.is_set():
                raise RuntimeError("Task cancelled before start.")
            stream.progress(f"starting {intent.value.replace('_', ' ')}...")
            stream.progress("executing command pipeline...")
            result = app.handle_text_command(
                command,
                input_mode="background",
                print_result=False,
            )
            if cancel_flag.is_set():
                raise RuntimeError("Task cancelled during execution.")
            stream.render_completion(result)
            summary = (result.summary or "")[:500]
            result_status = getattr(result.status, "value", str(result.status))
            phase = TaskPhase.COMPLETED if result_status == "success" else TaskPhase.FAILED
            severity = "info" if phase == TaskPhase.COMPLETED else "error"
            notification_id = self._notify_task_finished(task_id, command, intent, result, summary)
        except Exception as exc:
            error_text = str(exc)
            logger.exception("Background task %s failed", task_id)
            stream.fail(error_text, result=result)
            phase = TaskPhase.CANCELLED if cancel_flag.is_set() else TaskPhase.FAILED
            if isinstance(exc, TimeoutError):
                phase = TaskPhase.TIMED_OUT
            summary = error_text[:500]
            severity = "error"
            try:
                from assistant.notifications import notify_runtime_degraded

                note = notify_runtime_degraded(
                    f"Background task {task_id} failed: {error_text[:120]}",
                    task_id=task_id,
                )
                notification_id = note.id
            except Exception:
                pass
        finally:
            related = _extract_reports(result) if result is not None else []
            errors = [error_text[:400]] if error_text else []
            self._lifecycle.finalize(
                task_id,
                phase=phase,
                summary=summary,
                severity=severity,
                errors=errors,
                related_reports=related,
                notification_id=notification_id,
            )
            set_current_task_id(None)
            stream.detach()
            with self._lock:
                self._futures.pop(task_id, None)
                self._cancel_flags.pop(task_id, None)

    def _notify_task_finished(
        self,
        task_id: int,
        command: str,
        intent: Intent,
        result: CommandResult,
        summary: str,
    ) -> int | None:
        try:
            from assistant.notifications import (
                notify_investigation_completed,
                notify_patch_workflow_completed,
                notify_replay_validation_passed,
            )

            if intent in {
                Intent.RECONSTRUCT_EXECUTION_FLOW,
                Intent.RUN_HISTORICAL_VALIDATION_SWEEP,
                Intent.SUMMARIZE_TRADING_HEALTH,
            }:
                note = notify_investigation_completed(
                    f"Task {task_id} completed: {command}",
                    summary=summary[:200],
                    task_id=task_id,
                )
                return note.id
            if intent == Intent.REPLAY_AFTER_PATCH and "PASSED" in (result.summary or "").upper():
                note = notify_replay_validation_passed(summary[:200], task_id=task_id)
                return note.id
            if intent == Intent.RUN_PATCH_WORKFLOW:
                note = notify_patch_workflow_completed(summary[:200], task_id=task_id)
                return note.id
        except Exception:
            pass
        return None

    def cancel_task(self, task_id: int) -> tuple[bool, str]:
        record = self._lifecycle.get(task_id)
        if record is None:
            return False, f"No task with id {task_id}."
        if record.phase.is_terminal:
            return False, f"Task {task_id} is {record.phase.value}; cannot cancel."
        self._lifecycle.cancel_requested(task_id)
        with self._lock:
            flag = self._cancel_flags.get(task_id)
            if flag is not None:
                flag.set()
        print(f"[RESULT] cancellation requested for task {task_id}", flush=True)
        return True, f"Cancellation requested for task {task_id}."

    def list_running(self) -> list[BackgroundTask]:
        records = self._lifecycle.list_active()
        return [BackgroundTask.from_record(r, lifecycle=self._lifecycle) for r in records]

    def list_completed(self) -> list[BackgroundTask]:
        records = self._lifecycle.list_by_phase({TaskPhase.COMPLETED})
        return [BackgroundTask.from_record(r, lifecycle=self._lifecycle) for r in records]

    def list_failed(self) -> list[BackgroundTask]:
        records = self._lifecycle.list_by_phase(
            {TaskPhase.FAILED, TaskPhase.TIMED_OUT, TaskPhase.CANCELLED}
        )
        return [BackgroundTask.from_record(r, lifecycle=self._lifecycle) for r in records]

    def list_recent_results(self, *, limit: int = 8) -> list[BackgroundTask]:
        records = self._lifecycle.list_recent(limit=limit)
        return [BackgroundTask.from_record(r, lifecycle=self._lifecycle) for r in records]

    def get_task(self, task_id: int) -> BackgroundTask | None:
        record = self._lifecycle.get(task_id)
        if record is None:
            return None
        return BackgroundTask.from_record(record, lifecycle=self._lifecycle)

    def get_last_completed(self) -> BackgroundTask | None:
        record = self._lifecycle.get_last_completed()
        if record is None:
            return None
        return BackgroundTask.from_record(record, lifecycle=self._lifecycle)

    def rerun_last(self, app: JarvisApp | None = None) -> tuple[int | None, str]:
        last = self.get_last_completed()
        if last is None:
            return None, "No completed background task to rerun."
        if app is None and self._app_ref is not None:
            app = self._app_ref()
        if app is None:
            return None, "No app context available to rerun task."
        intent = Intent(last.intent)
        task_id = self.submit(app, last.command, intent)
        return task_id, f"Rerunning task {last.id} as new task {task_id}."

    def explain_last_result(self) -> str:
        return self._lifecycle.explain_last_result()

    def reopen_task_result(self, task_id: int) -> str:
        return self._lifecycle.reopen_result(task_id)

    def format_task_list(self, tasks: list[BackgroundTask], *, title: str) -> str:
        records: list[TaskRecord] = []
        for task in tasks:
            record = self._lifecycle.get(task.id)
            if record is not None:
                records.append(record)
        return self._lifecycle.format_list(records, title=title)

    def _monitor_loop(self) -> None:
        while True:
            try:
                self._check_stuck_tasks()
            except Exception as exc:
                logger.debug("Background task monitor: %s", exc)
            time.sleep(15.0)

    def _check_stuck_tasks(self) -> None:
        for record in self._lifecycle.list_active():
            elapsed = self._lifecycle.live_elapsed(record)
            if elapsed < STUCK_TASK_SECONDS:
                continue
            msg = f"Task {record.id} may be stuck ({elapsed:.0f}s): {record.command[:80]}"
            logger.warning(msg)
            print(f"[PROGRESS] WARNING {msg}", flush=True)
            touch_task_progress(f"still running ({elapsed:.0f}s)", task_id=record.id)
            if elapsed >= TASK_TIMEOUT_SECONDS:
                with self._lock:
                    flag = self._cancel_flags.get(record.id)
                    if flag is not None:
                        flag.set()


def get_engine() -> BackgroundTaskEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = BackgroundTaskEngine()
        return _engine


def reset_background_engine_for_tests() -> None:
    global _engine
    with _engine_lock:
        _engine = None


def _extract_reports(result: CommandResult) -> list[str]:
    reports: list[str] = []
    data = result.data or {}
    for key in ("report", "report_path", "report_json", "report_markdown"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            reports.append(value.strip())
    for line in (result.summary or "").splitlines():
        if "report:" in line.lower():
            reports.append(line.split("report:", 1)[-1].strip())
    return reports[:8]
