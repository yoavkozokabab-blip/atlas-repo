"""Task agent markdown reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT
from task_agent.models import TaskSession, TaskStatus
from task_agent.report_templates import build_engineering_report


def reports_dir() -> Path:
    path = PROJECT_ROOT / "reports" / "task_agent"
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"task_{stamp}.md"


def build_report_markdown(session: TaskSession) -> str:
    return build_engineering_report(session)


def write_task_report(session: TaskSession) -> Path:
    """Write report to reports/task_agent/task_YYYYMMDD_HHMMSS.md"""
    content = build_report_markdown(session)
    out = reports_dir() / report_filename()
    out.write_text(content, encoding="utf-8")
    session.report_path = str(out)
    session.status = TaskStatus.COMPLETE
    return out
