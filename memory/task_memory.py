"""Persistent structured task memory across restarts (Phase 50/51)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.memory.task")

TASK_MEMORY_PATH = DATA_DIR / "task_memory.json"
_MAX_ITEMS = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "current_investigation": {"title": "", "started_at": "", "pinned": False},
        "current_blocker": "",
        "recent_investigations": [],
        "recent_reports": [],
        "recent_symbols": [],
        "open_workflows": [],
        "pending_patches": [],
        "pending_workflow": "",
        "recent_failures": [],
        "runtime_incidents": [],
        "last_dashboard_open": "",
        "last_task": "",
        "last_intent": "",
        "completed_cleared_at": "",
        "updated_at": "",
    }


def _load() -> dict[str, Any]:
    if not TASK_MEMORY_PATH.exists():
        return _default_state()
    data = load_json(TASK_MEMORY_PATH, default=_default_state(), validator=lambda x: x if isinstance(x, dict) else None)
    base = _default_state()
    base.update(data)
    if not isinstance(base.get("current_investigation"), dict):
        base["current_investigation"] = {"title": str(base.get("current_investigation") or ""), "started_at": "", "pinned": False}
    return base


def _save(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    atomic_write_json(TASK_MEMORY_PATH, data)


def _push_unique(items: list[str], value: str, *, limit: int = _MAX_ITEMS) -> list[str]:
    value = (value or "").strip()
    if not value:
        return items
    out = [value] + [x for x in items if x != value]
    return out[:limit]


def record_command(intent: str, summary: str, *, symbol: str = "", report: str = "") -> None:
    try:
        data = _load()
        data["last_intent"] = intent
        data["last_task"] = summary[:200]
        inv_keywords = (
            "investigation",
            "replay",
            "patch",
            "execution",
            "audit",
            "trace",
            "compare",
            "validate",
            "blocker",
        )
        lower = f"{intent} {summary}".lower()
        if any(k in lower for k in inv_keywords):
            inv = data["current_investigation"]
            if not inv.get("title") or not inv.get("pinned"):
                inv["title"] = summary[:200] or intent
                if not inv.get("started_at"):
                    inv["started_at"] = _now()
            data["recent_investigations"] = _push_unique(list(data.get("recent_investigations") or []), summary[:120] or intent)
        if "blocker" in lower:
            data["current_blocker"] = summary[:160]
        if report:
            data["recent_reports"] = _push_unique(list(data.get("recent_reports") or []), report)
        if symbol:
            data["recent_symbols"] = _push_unique(list(data.get("recent_symbols") or []), symbol.upper())
        if "fail" in summary.lower() or "error" in summary.lower():
            data["recent_failures"] = _push_unique(list(data.get("recent_failures") or []), f"{intent}: {summary[:120]}")
        if "patch" in lower or "workflow" in lower:
            data["pending_workflow"] = summary[:160] or intent
            data["pending_patches"] = _push_unique(list(data.get("pending_patches") or []), summary[:120])
        if intent in {"open_trading_dashboard", "restart_dashboard"} or "dashboard" in lower:
            data["last_dashboard_open"] = _now()
        if "incident" in lower or intent in {"recover_overlay", "recover_voice_system", "validate_runtime_integrity"}:
            data["runtime_incidents"] = _push_unique(list(data.get("runtime_incidents") or []), summary[:120])
        _save(data)
    except Exception as exc:
        logger.debug("record_command task memory failed: %s", exc)


def show_memory_state() -> str:
    data = _load()
    inv = data.get("current_investigation") or {}
    lines = [
        "Structured memory state:",
        f"  current investigation: {inv.get('title') or 'none'}",
        f"  investigation pinned: {inv.get('pinned', False)}",
        f"  investigation started: {inv.get('started_at') or 'n/a'}",
        f"  current blocker: {data.get('current_blocker') or 'none'}",
        f"  pending workflow: {data.get('pending_workflow') or 'none'}",
        f"  last dashboard open: {data.get('last_dashboard_open') or 'never'}",
        f"  recent symbols: {', '.join((data.get('recent_symbols') or [])[:8]) or 'none'}",
        f"  recent reports: {len(data.get('recent_reports') or [])}",
        f"  runtime incidents: {len(data.get('runtime_incidents') or [])}",
        f"  last intent: {data.get('last_intent') or 'none'}",
        f"  updated: {data.get('updated_at') or 'never'}",
    ]
    return "\n".join(lines)


def what_was_i_doing() -> str:
    return show_memory_state()


def get_last_investigation() -> str:
    data = _load()
    inv = data.get("current_investigation") or {}
    return str(inv.get("title") or "")


def pin_investigation(title: str = "") -> str:
    data = _load()
    inv = data["current_investigation"]
    value = (title or inv.get("title") or data.get("last_task") or "").strip()
    if not value:
        return "Nothing to pin. Start an investigation first."
    inv["title"] = value[:200]
    inv["pinned"] = True
    if not inv.get("started_at"):
        inv["started_at"] = _now()
    data["current_investigation"] = inv
    _save(data)
    return f"Pinned investigation: {value}"


def clear_completed_task() -> str:
    data = _load()
    data["last_task"] = ""
    if not (data.get("current_investigation") or {}).get("pinned"):
        data["current_investigation"] = {"title": "", "started_at": "", "pinned": False}
    data["current_blocker"] = ""
    data["pending_workflow"] = ""
    data["completed_cleared_at"] = _now()
    _save(data)
    return "Cleared completed task context (pinned investigation preserved)."


def resume_last_task() -> str:
    data = _load()
    last = data.get("last_task") or get_last_investigation()
    if not last:
        return "No saved task to resume."
    return f"Resume hint: re-run related command for '{last}'"


def show_recent_investigations() -> str:
    data = _load()
    items = list(data.get("recent_investigations") or [])[:15]
    if not items:
        return "No recent investigations recorded."
    lines = ["Recent investigations:"]
    lines.extend(f"  - {item}" for item in items)
    return "\n".join(lines)


def continue_investigation() -> str:
    last = get_last_investigation()
    if not last:
        return "No investigation in progress. Start with inspect project or audit execution path."
    return f"Continue from: {last}\nSuggested: show investigation summary, replay latest signal, show execution blockers"


def continue_trading_investigation() -> str:
    data = _load()
    blocker = data.get("current_blocker") or "unknown"
    return "\n".join(
        [
            "Continue trading investigation:",
            f"  focus: {get_last_investigation() or 'trading execution path'}",
            f"  current blocker: {blocker}",
            "  next commands:",
            "    - summarize trading health",
            "    - show execution blockers",
            "    - show top operational blockers",
            "    - replay latest signal",
        ]
    )


def open_last_report() -> str:
    data = _load()
    reports = list(data.get("recent_reports") or [])
    if not reports:
        from computer_control.desktop_controller import open_latest_report

        return open_latest_report()
    latest = reports[0]
    path = Path(latest)
    if path.exists():
        import os

        os.startfile(path)  # noqa: S606
        return f"Opened last report: {path}"
    from computer_control.desktop_controller import open_latest_report

    return open_latest_report()
