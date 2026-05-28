"""Live result streaming for console and overlay (Phase 52)."""

from __future__ import annotations

import re
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.types import CommandResult

_current_stream: ContextVar[ResultStream | None] = ContextVar("jarvis_result_stream", default=None)


@dataclass
class ResultPanel:
    title: str = ""
    severity: str = "info"
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    suggested_next_action: str = ""
    related_reports: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class ResultStream:
    """Structured live output for a single command execution."""

    def __init__(self, command: str, *, task_id: int | None = None) -> None:
        self.command = command.strip()
        self.task_id = task_id
        self._started = time.perf_counter()
        self._token: Token | None = None
        self._panel = ResultPanel(title=self.command)
        self._finished = False

    @classmethod
    def start(cls, command: str, *, task_id: int | None = None) -> ResultStream:
        stream = cls(command, task_id=task_id)
        stream._attach()
        return stream

    def __enter__(self) -> ResultStream:
        self._attach()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._finished:
            self.detach()

    def _attach(self) -> None:
        if self._token is None:
            self._token = _current_stream.set(self)
        try:
            from ui.overlay_app import notify_overlay_task_started

            notify_overlay_task_started(
                command=self.command,
                task_id=self.task_id,
            )
        except Exception:
            pass

    def detach(self) -> None:
        if self._token is not None:
            _current_stream.reset(self._token)
            self._token = None

    def progress(self, message: str) -> None:
        msg = message.strip()
        if not msg:
            return
        print(f"[PROGRESS] {msg}", flush=True)
        try:
            from runtime.task_lifecycle import touch_task_progress

            touch_task_progress(msg, task_id=self.task_id)
        except Exception:
            pass
        try:
            from ui.overlay_app import notify_overlay_task_progress

            notify_overlay_task_progress(
                command=self.command,
                task_id=self.task_id,
                progress=msg,
            )
        except Exception:
            pass

    def result_line(self, message: str, *, severity: str = "info") -> None:
        msg = message.strip()
        if not msg:
            return
        print(f"[RESULT] {msg}", flush=True)
        self._panel.evidence.append(msg)
        try:
            from runtime.task_lifecycle import get_task_lifecycle

            if self.task_id is not None:
                get_task_lifecycle().record_result_line(self.task_id, msg, severity=severity)
        except Exception:
            pass
        if severity in {"warning", "error", "critical"}:
            self._panel.severity = severity

    def set_summary(self, summary: str) -> None:
        self._panel.summary = (summary or "").strip()[:800]

    def set_next_action(self, action: str) -> None:
        self._panel.suggested_next_action = (action or "").strip()[:400]

    def add_related_report(self, path: str) -> None:
        safe = (path or "").strip()
        if safe and safe not in self._panel.related_reports:
            self._panel.related_reports.append(safe)

    def render_panel(self, result: CommandResult | None = None) -> None:
        elapsed = time.perf_counter() - self._started
        self._panel.elapsed_seconds = elapsed
        if result is not None:
            self._ingest_result(result)
        lines = [
            "--- Result ---",
            f"title: {self._panel.title or self.command}",
            f"severity: {self._panel.severity}",
        ]
        if self._panel.summary:
            for chunk in self._panel.summary.splitlines()[:6]:
                lines.append(f"summary: {chunk[:120]}")
        for item in self._panel.evidence[:8]:
            lines.append(f"evidence: {item[:120]}")
        if self._panel.suggested_next_action:
            lines.append(f"next: {self._panel.suggested_next_action[:120]}")
        for report in self._panel.related_reports[:4]:
            lines.append(f"report: {report[:120]}")
        lines.append(f"elapsed: {elapsed:.1f}s")
        lines.append("--------------")
        print("\n".join(lines), flush=True)

    def render_completion(self, result: CommandResult | None) -> None:
        if result is not None:
            self._ingest_result(result)
            if result.summary:
                preview = result.summary.splitlines()[0][:160]
                self.result_line(preview, severity=self._severity_from_result(result))
        self.render_panel(result)
        status = "success"
        if result is not None:
            status = getattr(result.status, "value", str(result.status))
        self.complete(status=status)

    def complete(self, *, status: str = "success", result: CommandResult | None = None) -> None:
        if self._finished:
            return
        elapsed = time.perf_counter() - self._started
        self._panel.elapsed_seconds = elapsed
        if result is not None:
            self._ingest_result(result)
        label = self.command
        if self.task_id is not None:
            label = f"task {self.task_id}: {label}"
        print(f"[COMPLETE] {label} ({elapsed:.1f}s) status={status}", flush=True)
        self._finished = True
        self.detach()
        try:
            from ui.overlay_app import notify_overlay_task_complete

            summary = self._panel.summary or (result.summary if result else "")
            notify_overlay_task_complete(
                command=self.command,
                task_id=self.task_id,
                summary=summary,
                status=status,
            )
        except Exception:
            pass

    def fail(self, error: str, *, result: CommandResult | None = None) -> None:
        msg = (error or "unknown error").strip()
        self._panel.severity = "error"
        self.result_line(msg, severity="error")
        if result is not None:
            self._ingest_result(result)
        self.render_panel(result)
        self.complete(status="failed", result=result)

    def _ingest_result(self, result: CommandResult) -> None:
        if not self._panel.summary and result.summary:
            self.set_summary(result.summary)
        if result.error:
            self.result_line(result.error, severity="error")
        data = result.data or {}
        for key in ("report", "report_path", "report_json", "report_markdown"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                self.add_related_report(value.strip())
        for suggestion in (result.next_suggestions or [])[:1]:
            if suggestion:
                self.set_next_action(str(suggestion))
        if not self._panel.suggested_next_action:
            self._panel.suggested_next_action = self._infer_next_action(result.summary or "")
        for match in re.findall(r"(?:report:|reports/[^\s]+)", result.summary or ""):
            self.add_related_report(match.replace("report:", "").strip())

    @staticmethod
    def _severity_from_result(result: CommandResult) -> str:
        status = getattr(result.status, "value", str(result.status))
        if status in {"failed", "blocked"}:
            return "error"
        if status in {"confirmation_required", "clarification_needed"}:
            return "warning"
        return "info"

    @staticmethod
    def _infer_next_action(summary: str) -> str:
        lower = summary.lower()
        if "stale" in lower and "position" in lower:
            return "Run show stale open positions or propose execution cleanup patch."
        if "blocker" in lower or "blocked" in lower:
            return "Run explain top execution blocker or reconstruct execution flow."
        if "confirmation required" in lower:
            return "Reply yes/no to confirm the pending action."
        if "dashboard" in lower and ("failed" in lower or "degraded" in lower):
            return "Run restart dashboard or show dashboard health."
        return ""


def get_stream() -> ResultStream | None:
    return _current_stream.get()


def stream_progress(message: str) -> None:
    stream = get_stream()
    if stream is not None:
        stream.progress(message)


def stream_result(message: str, *, severity: str = "info") -> None:
    stream = get_stream()
    if stream is not None:
        stream.result_line(message, severity=severity)

