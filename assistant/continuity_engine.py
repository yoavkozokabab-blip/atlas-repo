"""Assistant continuity across sessions (Phase 53)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json
from core.session import SessionState
from runtime.task_lifecycle import TaskRecord

logger = setup_logger("jarvis.assistant.continuity")

CONTINUITY_PATH = DATA_DIR / "assistant_continuity.json"
ASSISTANT_STATE_REPORT_DIR = PROJECT_ROOT / "reports" / "assistant_state"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "current_investigation": "",
        "pending_tasks": [],
        "recent_blockers": [],
        "latest_dashboard_state": "",
        "latest_reports": [],
        "recent_symbols": [],
        "operational_risks": [],
        "unresolved_incidents": [],
        "last_session_summary": "",
        "last_started_at": "",
        "last_ended_at": "",
        "updated_at": "",
    }


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(CONTINUITY_PATH, default=_default_state(), validator=_validate)
    base = _default_state()
    base.update(state)
    return base


def _save(data: dict[str, Any]) -> None:
    data["updated_at"] = _now()
    atomic_write_json(CONTINUITY_PATH, data)
    try:
        ASSISTANT_STATE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = ASSISTANT_STATE_REPORT_DIR / f"{ts}_assistant_state.json"
        path.write_text(
            __import__("json").dumps(data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Assistant state report skipped: %s", exc)


def _push_unique(items: list[str], value: str, *, limit: int = 20) -> list[str]:
    value = (value or "").strip()
    if not value:
        return items
    return [value] + [x for x in items if x != value][: limit - 1]


def record_task_completion(task: TaskRecord) -> None:
    data = _load()
    if "investigation" in task.intent or "trading" in task.intent or "execution" in task.intent:
        data["current_investigation"] = task.command[:200]
    summary = task.result_summary or task.command
    data["last_session_summary"] = summary[:400]
    for line in task.evidence:
        if "blocker" in line.lower():
            data["recent_blockers"] = _push_unique(data["recent_blockers"], line[:160])
    for report in task.related_reports:
        data["latest_reports"] = _push_unique(data["latest_reports"], report)
    if task.severity in {"warning", "error", "critical"}:
        data["unresolved_incidents"] = _push_unique(
            data["unresolved_incidents"],
            f"{task.command}: {summary[:120]}",
        )
    if task.phase.value == "completed" and task.command in data.get("pending_tasks", []):
        data["pending_tasks"] = [t for t in data["pending_tasks"] if t != task.command]
    _save(data)
    try:
        from memory.task_memory import record_command

        record_command(task.intent, summary, report=task.related_reports[0] if task.related_reports else "")
    except Exception:
        pass


def note_session_start() -> None:
    data = _load()
    data["last_started_at"] = _now()
    _save(data)


def continue_previous_session() -> str:
    data = _load()
    session = SessionState.load()
    lines = ["Continuing previous assistant session:"]
    investigation = data.get("current_investigation") or ""
    if investigation:
        lines.append(f"  investigation: {investigation}")
    else:
        lines.append("  investigation: none recorded")
    blockers = data.get("recent_blockers") or []
    if blockers:
        lines.append(f"  recent blockers: {blockers[0]}")
    pending = data.get("pending_tasks") or []
    if pending:
        lines.append(f"  pending tasks: {', '.join(pending[:3])}")
    if session.last_intent:
        lines.append(f"  last intent: {session.last_intent}")
    if session.last_result_summary:
        lines.append(f"  last result: {session.last_result_summary[:160]}")
    if investigation and blockers:
        lines.append(
            f"\nYou were investigating {investigation} with focus on {blockers[0]}."
        )
    elif investigation:
        lines.append(f"\nYou were investigating {investigation}.")
    lines.append("Try: resume latest investigation | summarize unresolved issues")
    return "\n".join(lines)


def summarize_unresolved_issues() -> str:
    data = _load()
    lines = ["Unresolved operational issues:"]
    incidents = data.get("unresolved_incidents") or []
    blockers = data.get("recent_blockers") or []
    risks = data.get("operational_risks") or []
    if not incidents and not blockers and not risks:
        lines.append("- none recorded in continuity store")
    for item in incidents[:5]:
        lines.append(f"- incident: {item}")
    for item in blockers[:5]:
        lines.append(f"- blocker: {item}")
    for item in risks[:5]:
        lines.append(f"- risk: {item}")
    try:
        from runtime.background_tasks import get_engine

        failed = get_engine().list_failed()
        for task in failed[:3]:
            lines.append(f"- failed task [{task.id}]: {task.result_summary[:100] or task.command}")
    except Exception:
        pass
    return "\n".join(lines)


def resume_latest_investigation() -> str:
    data = _load()
    investigation = (data.get("current_investigation") or "").strip()
    if not investigation:
        try:
            from memory.task_memory import continue_trading_investigation

            return continue_trading_investigation()
        except Exception:
            return "No latest investigation recorded. Try summarize trading health."
    return (
        f"Resuming investigation: {investigation}\n"
        f"Suggested commands:\n"
        f"  - {investigation}\n"
        f"  - explain top execution blocker\n"
        f"  - reconstruct execution flow"
    )


def what_changed_since_last_session() -> str:
    data = _load()
    session = SessionState.load()
    lines = ["Changes since last session:"]
    if data.get("last_started_at"):
        lines.append(f"  last session started: {data['last_started_at']}")
    if data.get("last_ended_at"):
        lines.append(f"  previous session ended: {data['last_ended_at']}")
    if session.last_intent:
        lines.append(f"  last command intent: {session.last_intent}")
    if data.get("last_session_summary"):
        lines.append(f"  last task summary: {data['last_session_summary'][:160]}")
    reports = data.get("latest_reports") or []
    if reports:
        lines.append(f"  latest report: {reports[0]}")
    try:
        from assistant.notifications import get_notification_store

        latest = get_notification_store().list_notifications(limit=3)
        for note in latest:
            lines.append(f"  notification [{note.id}]: {note.title}")
    except Exception:
        pass
    if len(lines) == 1:
        lines.append("  - no continuity delta recorded yet")
    return "\n".join(lines)


def get_overlay_snapshot() -> dict[str, str]:
    data = _load()
    snapshot: dict[str, str] = {}
    if data.get("current_investigation"):
        snapshot["investigation"] = str(data["current_investigation"])[:100]
    blockers = data.get("recent_blockers") or []
    if blockers:
        snapshot["blockers"] = str(blockers[0])[:100]
    incidents = data.get("unresolved_incidents") or []
    if incidents:
        snapshot["unresolved"] = str(incidents[0])[:100]
    return snapshot
