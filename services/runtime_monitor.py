"""Runtime stability monitor and timeout helpers."""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, TypeVar

from config import (
    RUNTIME_DEADLOCK_SECONDS,
    RUNTIME_EVENT_LOOP_LAG_WARN_SECONDS,
    RUNTIME_MEMORY_GROWTH_WARN_MB,
    RUNTIME_MEMORY_GROWTH_WINDOW_SECONDS,
    RUNTIME_MONITOR_INTERVAL_SECONDS,
    RUNTIME_MONITOR_STATUS_PATH,
)
from core.logger import setup_logger

logger = setup_logger("jarvis.services.runtime_monitor")

T = TypeVar("T")


class OperationTimeoutError(TimeoutError):
    """Raised when a guarded runtime operation exceeds its configured timeout."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _thread_frame(thread_id: int | None) -> str:
    if thread_id is None:
        return ""
    frame = sys._current_frames().get(thread_id)
    if frame is None:
        return ""
    code = frame.f_code
    return f"{Path(code.co_filename).name}:{code.co_name}:{frame.f_lineno}"


@dataclass
class OperationRecord:
    token: str
    name: str
    started_monotonic: float
    started_at: str
    timeout_seconds: float | None
    thread_name: str
    thread_id: int | None = None
    detail: str = ""

    def snapshot(self, now: float) -> dict[str, Any]:
        return {
            "token": self.token,
            "name": self.name,
            "age_seconds": round(max(0.0, now - self.started_monotonic), 3),
            "timeout_seconds": self.timeout_seconds,
            "thread": self.thread_name,
            "thread_id": self.thread_id,
            "frame": _thread_frame(self.thread_id),
            "started_at": self.started_at,
            "detail": self.detail,
        }


@dataclass
class RuntimeStabilityMonitor:
    """Tracks runtime liveness, slow operations, thread state, and memory growth."""

    interval_seconds: float = RUNTIME_MONITOR_INTERVAL_SECONDS
    status_path: Path = RUNTIME_MONITOR_STATUS_PATH
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _operations: dict[str, OperationRecord] = field(default_factory=dict, init=False, repr=False)
    _timeouts: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=50), init=False, repr=False)
    _recoveries: Deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100), init=False, repr=False)
    _heartbeats: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _memory_samples: Deque[tuple[float, int]] = field(default_factory=lambda: deque(maxlen=120), init=False, repr=False)
    _last_tick_monotonic: float | None = field(default=None, init=False, repr=False)
    _last_event_loop_lag: float = field(default=0.0, init=False, repr=False)
    _last_status: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-runtime-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Runtime stability monitor started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None

    def reset(self) -> None:
        with self._lock:
            self._operations.clear()
            self._timeouts.clear()
            self._recoveries.clear()
            self._heartbeats.clear()
            self._memory_samples.clear()
            self._last_tick_monotonic = None
            self._last_event_loop_lag = 0.0
            self._last_status = {}

    def heartbeat(self, name: str) -> None:
        with self._lock:
            self._heartbeats[name] = time.monotonic()

    def begin_operation(
        self,
        name: str,
        *,
        timeout_seconds: float | None = None,
        detail: str = "",
    ) -> str:
        thread = threading.current_thread()
        token = f"{name}:{int(time.time() * 1000)}:{thread.ident or 0}"
        rec = OperationRecord(
            token=token,
            name=name,
            started_monotonic=time.monotonic(),
            started_at=_utc_now(),
            timeout_seconds=float(timeout_seconds) if timeout_seconds else None,
            thread_name=thread.name,
            thread_id=thread.ident,
            detail=detail[:300],
        )
        with self._lock:
            self._operations[token] = rec
        return token

    def attach_operation_thread(self, token: str, thread: threading.Thread) -> None:
        with self._lock:
            rec = self._operations.get(token)
            if rec is not None:
                rec.thread_name = thread.name
                rec.thread_id = thread.ident

    def end_operation(self, token: str) -> None:
        with self._lock:
            self._operations.pop(token, None)

    def record_timeout(
        self,
        name: str,
        *,
        timeout_seconds: float,
        detail: str = "",
    ) -> None:
        event = {
            "at": _utc_now(),
            "name": name,
            "timeout_seconds": float(timeout_seconds),
            "detail": detail[:300],
        }
        with self._lock:
            self._timeouts.append(event)
        logger.warning("%s timed out after %.1fs", name, timeout_seconds)

    def retract_last_timeout(self, name: str) -> bool:
        """Remove the most recent timeout event when recovery succeeded (e.g. COM hang)."""
        with self._lock:
            if not self._timeouts:
                return False
            last = self._timeouts[-1]
            if last.get("name") != name:
                return False
            self._timeouts.pop()
            return True

    def record_recovery(
        self,
        component: str,
        action: str,
        *,
        reason: str,
        ok: bool = True,
        detail: str = "",
    ) -> None:
        event = {
            "at": _utc_now(),
            "component": component,
            "action": action,
            "reason": reason[:300],
            "ok": bool(ok),
            "detail": detail[:500],
        }
        with self._lock:
            self._recoveries.append(event)
        log = logger.info if ok else logger.warning
        log("Recovery %s/%s ok=%s reason=%s", component, action, ok, reason)

    def run_once(self) -> dict[str, Any]:
        now = time.monotonic()
        self._update_event_loop_lag(now)
        memory = self._collect_memory(now)
        threads = self._collect_threads()

        with self._lock:
            operations = [op.snapshot(now) for op in self._operations.values()]
            timeouts = list(self._timeouts)[-10:]
            recoveries = list(self._recoveries)[-20:]
            heartbeats = {
                name: round(max(0.0, now - ts), 3)
                for name, ts in sorted(self._heartbeats.items())
            }

        issues = self._detect_issues(
            operations=operations,
            heartbeats=heartbeats,
            memory=memory,
        )
        status = {
            "updated_at": _utc_now(),
            "overall": "critical" if any(i["severity"] == "critical" for i in issues)
            else ("warning" if issues else "ok"),
            "issues": issues,
            "event_loop": {
                "monitor_lag_seconds": round(self._last_event_loop_lag, 3),
                "warn_after_seconds": RUNTIME_EVENT_LOOP_LAG_WARN_SECONDS,
            },
            "threads": threads,
            "active_operations": operations,
            "timeouts": timeouts,
            "recoveries": recoveries,
            "heartbeats_age_seconds": heartbeats,
            "memory": memory,
        }
        self._write_status(status)
        with self._lock:
            self._last_status = status
        return status

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._last_status:
                return dict(self._last_status)
        return self.load_status(self.status_path)

    def _loop(self) -> None:
        while not self._stop.wait(max(1.0, float(self.interval_seconds))):
            self.heartbeat("runtime_monitor")
            try:
                self.run_once()
            except Exception as exc:
                logger.warning("Runtime monitor tick failed: %s", exc)

    def _update_event_loop_lag(self, now: float) -> None:
        with self._lock:
            if self._last_tick_monotonic is None:
                self._last_event_loop_lag = 0.0
            else:
                expected = self._last_tick_monotonic + max(1.0, float(self.interval_seconds))
                self._last_event_loop_lag = max(0.0, now - expected)
            self._last_tick_monotonic = now

    def _collect_threads(self) -> dict[str, Any]:
        all_threads = threading.enumerate()
        jarvis_threads = [
            {
                "name": t.name,
                "ident": t.ident,
                "daemon": t.daemon,
                "alive": t.is_alive(),
                "frame": _thread_frame(t.ident),
            }
            for t in all_threads
            if t.name.startswith("jarvis")
        ]
        by_name: dict[str, int] = {}
        for t in jarvis_threads:
            by_name[t["name"]] = by_name.get(t["name"], 0) + 1
        return {
            "total": len(all_threads),
            "jarvis_total": len(jarvis_threads),
            "jarvis_by_name": by_name,
            "jarvis_threads": jarvis_threads,
        }

    def _collect_memory(self, now: float) -> dict[str, Any]:
        rss_bytes = 0
        try:
            import psutil

            rss_bytes = int(psutil.Process().memory_info().rss)
        except Exception:
            rss_bytes = 0

        with self._lock:
            if rss_bytes > 0:
                self._memory_samples.append((now, rss_bytes))
            samples = list(self._memory_samples)

        rss_mb = rss_bytes / (1024 * 1024) if rss_bytes else 0.0
        growth_mb = 0.0
        per_minute_mb = 0.0
        if len(samples) >= 2:
            cutoff = now - max(1.0, RUNTIME_MEMORY_GROWTH_WINDOW_SECONDS)
            window = [(ts, rss) for ts, rss in samples if ts >= cutoff]
            if len(window) >= 2:
                first_ts, first_rss = window[0]
                last_ts, last_rss = window[-1]
                growth_mb = (last_rss - first_rss) / (1024 * 1024)
                elapsed_min = max((last_ts - first_ts) / 60.0, 1e-6)
                per_minute_mb = growth_mb / elapsed_min

        return {
            "rss_mb": round(rss_mb, 2),
            "growth_window_seconds": RUNTIME_MEMORY_GROWTH_WINDOW_SECONDS,
            "growth_mb": round(growth_mb, 2),
            "growth_mb_per_minute": round(per_minute_mb, 2),
            "warn_growth_mb": RUNTIME_MEMORY_GROWTH_WARN_MB,
            "sample_count": len(samples),
        }

    def _detect_issues(
        self,
        *,
        operations: list[dict[str, Any]],
        heartbeats: dict[str, float],
        memory: dict[str, Any],
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if self._last_event_loop_lag >= RUNTIME_EVENT_LOOP_LAG_WARN_SECONDS:
            issues.append(
                {
                    "severity": "warning",
                    "source": "event_loop",
                    "message": (
                        "Runtime monitor observed scheduler lag "
                        f"{self._last_event_loop_lag:.1f}s."
                    ),
                }
            )
        for op in operations:
            timeout = op.get("timeout_seconds")
            age = float(op.get("age_seconds") or 0.0)
            if timeout and age >= float(timeout):
                issues.append(
                    {
                        "severity": "critical",
                        "source": "operation_timeout",
                        "message": f"{op['name']} running for {age:.1f}s.",
                        "operation": op,
                    }
                )
            if age >= RUNTIME_DEADLOCK_SECONDS:
                issues.append(
                    {
                        "severity": "critical",
                        "source": "deadlock_suspect",
                        "message": f"{op['name']} appears stuck for {age:.1f}s.",
                        "operation": op,
                    }
                )
        for name, age in heartbeats.items():
            if age >= RUNTIME_DEADLOCK_SECONDS:
                issues.append(
                    {
                        "severity": "warning",
                        "source": "stale_heartbeat",
                        "message": f"{name} heartbeat stale for {age:.1f}s.",
                    }
                )
        if float(memory.get("growth_mb") or 0.0) >= RUNTIME_MEMORY_GROWTH_WARN_MB:
            issues.append(
                {
                    "severity": "warning",
                    "source": "memory_growth",
                    "message": (
                        "RSS grew "
                        f"{memory['growth_mb']:.1f} MB over "
                        f"{memory['growth_window_seconds']:.0f}s."
                    ),
                }
            )
        return issues

    def _write_status(self, status: dict[str, Any]) -> None:
        try:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            self.status_path.write_text(
                json.dumps(status, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.debug("Runtime monitor status write failed: %s", exc)

    @staticmethod
    def load_status(path: Path | None = None) -> dict[str, Any]:
        p = path or RUNTIME_MONITOR_STATUS_PATH
        if not p.is_file():
            return {
                "overall": "unknown",
                "issues": [],
                "summary": "Runtime monitor has not written status yet.",
            }
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "overall": "warning",
                "issues": [{"severity": "warning", "source": "status", "message": str(exc)}],
            }


_monitor = RuntimeStabilityMonitor()


def get_runtime_monitor() -> RuntimeStabilityMonitor:
    return _monitor


def reset_runtime_monitor() -> None:
    _monitor.reset()


def run_with_timeout(
    name: str,
    timeout_seconds: float | None,
    func: Callable[..., T],
    *args: Any,
    detail: str = "",
    on_timeout: Callable[[OperationTimeoutError], None] | None = None,
    **kwargs: Any,
) -> T:
    """Run a blocking operation on a daemon worker and return before it can hang callers."""
    monitor = get_runtime_monitor()
    if timeout_seconds is None or float(timeout_seconds) <= 0:
        token = monitor.begin_operation(name, timeout_seconds=None, detail=detail)
        try:
            return func(*args, **kwargs)
        finally:
            monitor.end_operation(token)

    timeout = float(timeout_seconds)
    result_q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
    token = monitor.begin_operation(name, timeout_seconds=timeout, detail=detail)

    def _target() -> None:
        try:
            result_q.put_nowait((True, func(*args, **kwargs)))
        except BaseException as exc:  # propagate operation errors to caller
            try:
                result_q.put_nowait((False, exc))
            except queue.Full:
                pass
        finally:
            monitor.end_operation(token)

    worker = threading.Thread(
        target=_target,
        name=f"jarvis-op-{name.replace('.', '-')}",
        daemon=True,
    )
    worker.start()
    monitor.attach_operation_thread(token, worker)

    try:
        ok, payload = result_q.get(timeout=timeout)
    except queue.Empty as exc:
        err = OperationTimeoutError(f"{name} timed out after {timeout:.1f}s")
        monitor.record_timeout(name, timeout_seconds=timeout, detail=detail)
        if on_timeout is not None:
            try:
                on_timeout(err)
            except Exception as callback_exc:
                logger.debug("%s timeout callback failed: %s", name, callback_exc)
        raise err from exc

    if ok:
        return payload
    raise payload
