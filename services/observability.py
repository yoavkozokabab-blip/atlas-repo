"""Phase A3 observability: traces, latency heatmaps, profiling, and failures."""

from __future__ import annotations

import json
import threading
import time
import traceback
import uuid
from collections import Counter, defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import (
    OBSERVABILITY_ENABLED,
    OBSERVABILITY_JSONL_PATH,
    OBSERVABILITY_LATENCY_BUCKETS_MS,
    OBSERVABILITY_MAX_MEMORY_EVENTS,
    OBSERVABILITY_TRACE_PATH,
)
from core.logger import setup_logger

logger = setup_logger("jarvis.services.observability")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value[:20]]
    if isinstance(value, dict):
        return {str(k)[:80]: _safe_value(v) for k, v in list(value.items())[:40]}
    return str(value)[:500]


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(k)[:80]: _safe_value(v) for k, v in payload.items()}


@dataclass
class LatencyHeatmap:
    buckets_ms: tuple[int, ...]
    counts: Counter[str] = field(default_factory=Counter)
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0

    def record(self, ms: float) -> str:
        value = max(0.0, float(ms))
        self.count += 1
        self.total_ms += value
        self.max_ms = max(self.max_ms, value)
        for bound in self.buckets_ms:
            if value <= bound:
                label = f"le_{bound}ms"
                self.counts[label] += 1
                return label
        label = f"gt_{self.buckets_ms[-1]}ms" if self.buckets_ms else "all"
        self.counts[label] += 1
        return label

    def to_dict(self) -> dict[str, Any]:
        avg = self.total_ms / self.count if self.count else 0.0
        return {
            "count": self.count,
            "avg_ms": round(avg, 2),
            "max_ms": round(self.max_ms, 2),
            "buckets": dict(self.counts),
        }


@dataclass
class TraceSpan:
    trace_id: str
    name: str
    started_monotonic: float
    started_at: str
    attrs: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None


class ObservabilityService:
    """Central in-memory + JSONL observability sink."""

    def __init__(
        self,
        *,
        event_path: Path = OBSERVABILITY_JSONL_PATH,
        trace_path: Path = OBSERVABILITY_TRACE_PATH,
        max_events: int = OBSERVABILITY_MAX_MEMORY_EVENTS,
    ) -> None:
        self.event_path = event_path
        self.trace_path = trace_path
        self.max_events = max(50, int(max_events))
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=self.max_events)
        self._traces: deque[dict[str, Any]] = deque(maxlen=self.max_events)
        self._active: dict[str, TraceSpan] = {}
        self._heatmaps: dict[str, LatencyHeatmap] = {}
        self._pipeline: dict[str, LatencyHeatmap] = {}
        self._failures: Counter[str] = Counter()
        self._failure_details: dict[str, dict[str, Any]] = {}
        self._overlay_frames = 0
        self._overlay_started = time.monotonic()
        self._overlay_last_fps = 0.0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._traces.clear()
            self._active.clear()
            self._heatmaps.clear()
            self._pipeline.clear()
            self._failures.clear()
            self._failure_details.clear()
            self._overlay_frames = 0
            self._overlay_started = time.monotonic()
            self._overlay_last_fps = 0.0

    def structured_log(self, event: str, **payload: Any) -> dict[str, Any]:
        record = {
            "ts": _now_iso(),
            "event": event,
            "payload": _safe_payload(payload),
        }
        with self._lock:
            self._events.append(record)
        self._append_jsonl(self.event_path, record)
        return record

    def start_trace(self, name: str, **attrs: Any) -> str:
        trace_id = uuid.uuid4().hex
        span = TraceSpan(
            trace_id=trace_id,
            name=name,
            started_monotonic=time.perf_counter(),
            started_at=_now_iso(),
            attrs=_safe_payload(attrs),
        )
        with self._lock:
            self._active[trace_id] = span
        self.structured_log("trace.started", trace_id=trace_id, name=name, **attrs)
        return trace_id

    def finish_trace(
        self,
        trace_id: str,
        *,
        status: str = "ok",
        error: str | None = None,
        **attrs: Any,
    ) -> dict[str, Any] | None:
        with self._lock:
            span = self._active.pop(trace_id, None)
        if span is None:
            return None
        duration_ms = (time.perf_counter() - span.started_monotonic) * 1000.0
        record = {
            "ts": _now_iso(),
            "trace_id": trace_id,
            "name": span.name,
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "started_at": span.started_at,
            "attrs": _safe_payload({**span.attrs, **attrs}),
        }
        if error:
            record["error"] = error[:500]
        tb = attrs.pop("error_traceback", None)
        if tb:
            record["error_traceback"] = str(tb)[:4000]
        with self._lock:
            self._traces.append(record)
        self.record_latency(f"trace.{span.name}", duration_ms)
        self._append_jsonl(self.trace_path, record)
        self.structured_log(
            "trace.finished",
            trace_id=trace_id,
            name=span.name,
            status=status,
            duration_ms=duration_ms,
            error=error,
        )
        return record

    @contextmanager
    def trace(self, name: str, **attrs: Any) -> Iterator[str]:
        trace_id = self.start_trace(name, **attrs)
        try:
            yield trace_id
        except Exception as exc:
            self.record_failure(component=name, error=exc)
            self.finish_trace(trace_id, status="failed", error=str(exc))
            raise
        else:
            self.finish_trace(trace_id, status="ok")

    def record_latency(self, metric: str, duration_ms: float, **labels: Any) -> None:
        key = metric.strip() or "unknown"
        with self._lock:
            heatmap = self._heatmaps.setdefault(
                key,
                LatencyHeatmap(tuple(OBSERVABILITY_LATENCY_BUCKETS_MS)),
            )
            bucket = heatmap.record(duration_ms)
        self.structured_log(
            "latency",
            metric=key,
            duration_ms=round(max(0.0, float(duration_ms)), 3),
            bucket=bucket,
            labels=labels,
        )

    def profile_stage(self, pipeline: str, stage: str, duration_ms: float, **attrs: Any) -> None:
        key = f"{pipeline}.{stage}".strip(".")
        with self._lock:
            heatmap = self._pipeline.setdefault(
                key,
                LatencyHeatmap(tuple(OBSERVABILITY_LATENCY_BUCKETS_MS)),
            )
            bucket = heatmap.record(duration_ms)
        self.structured_log(
            "pipeline.stage",
            pipeline=pipeline,
            stage=stage,
            duration_ms=round(max(0.0, float(duration_ms)), 3),
            bucket=bucket,
            attrs=attrs,
        )

    def record_command_lifecycle(
        self,
        phase: str,
        *,
        trace_id: str | None = None,
        input_mode: str = "",
        intent: str = "",
        status: str = "",
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "phase": phase,
            "trace_id": trace_id,
            "input_mode": input_mode,
            "intent": intent,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        }
        self.structured_log("command.lifecycle", **payload)
        if duration_ms is not None:
            self.record_latency("command.lifecycle", duration_ms, phase=phase, intent=intent)
        if error:
            self.record_failure(component="command", error=error, context=payload)

    def record_overlay_frame(self, *, sample_seconds: float = 5.0) -> float:
        now = time.monotonic()
        sample_ready = False
        with self._lock:
            self._overlay_frames += 1
            elapsed = now - self._overlay_started
            if elapsed >= max(0.25, float(sample_seconds)):
                self._overlay_last_fps = self._overlay_frames / max(elapsed, 1e-6)
                self._overlay_frames = 0
                self._overlay_started = now
                fps = self._overlay_last_fps
                sample_ready = True
            else:
                fps = self._overlay_last_fps
        if sample_ready:
            self.structured_log("overlay.fps", fps=round(fps, 2))
        return fps

    def record_failure(
        self,
        *,
        component: str,
        error: BaseException | str,
        context: dict[str, Any] | None = None,
    ) -> str:
        message = str(error)
        kind = type(error).__name__ if isinstance(error, BaseException) else "error"
        fingerprint = f"{component}:{kind}:{message[:120]}"
        stack = ""
        if isinstance(error, BaseException):
            stack = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            ).strip()
        detail = {
            "component": component,
            "kind": kind,
            "message": message[:500],
            "last_seen": _now_iso(),
            "stack": stack[:1000],
            "context": _safe_payload(context or {}),
        }
        with self._lock:
            self._failures[fingerprint] += 1
            detail["count"] = self._failures[fingerprint]
            self._failure_details[fingerprint] = detail
        self.structured_log("failure", fingerprint=fingerprint, **detail)
        return fingerprint

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": OBSERVABILITY_ENABLED,
                "events": list(self._events)[-20:],
                "traces": list(self._traces)[-20:],
                "active_traces": {
                    trace_id: {
                        "name": span.name,
                        "age_ms": round((time.perf_counter() - span.started_monotonic) * 1000.0, 2),
                        "attrs": dict(span.attrs),
                    }
                    for trace_id, span in self._active.items()
                },
                "latency_heatmaps": {
                    name: heatmap.to_dict() for name, heatmap in self._heatmaps.items()
                },
                "pipeline_profiles": {
                    name: heatmap.to_dict() for name, heatmap in self._pipeline.items()
                },
                "failures": {
                    fp: dict(detail)
                    for fp, detail in sorted(
                        self._failure_details.items(),
                        key=lambda kv: int(kv[1].get("count", 0)),
                        reverse=True,
                    )[:20]
                },
                "overlay": {
                    "fps": round(self._overlay_last_fps, 2),
                    "frames_pending_sample": self._overlay_frames,
                },
                "event_log_path": str(self.event_path),
                "trace_log_path": str(self.trace_path),
            }

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        if not OBSERVABILITY_ENABLED:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError as exc:
            logger.debug("Observability JSONL write failed: %s", exc)


_service = ObservabilityService()


def get_observability() -> ObservabilityService:
    return _service


def reset_observability() -> None:
    _service.reset()


def structured_log(event: str, **payload: Any) -> dict[str, Any]:
    return _service.structured_log(event, **payload)
