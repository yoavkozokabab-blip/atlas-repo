"""Operational intelligence timeline (Phase 54)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.intelligence_timeline")

TIMELINE_PATH = DATA_DIR / "intelligence_timeline.json"
TIMELINE_REPORT_DIR = PROJECT_ROOT / "reports" / "intelligence_timeline"
MAX_ENTRIES = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"entries": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(TIMELINE_PATH, default=_default_state(), validator=_validate)
    if not isinstance(state.get("entries"), list):
        state["entries"] = []
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(TIMELINE_PATH, state)


def append_timeline_entry(
    category: str,
    message: str,
    *,
    severity: str = "info",
    source: str = "autonomous",
    metadata: dict[str, Any] | None = None,
) -> None:
    state = _load()
    entry = {
        "timestamp": _now(),
        "category": category[:60],
        "message": message[:400],
        "severity": severity,
        "source": source[:60],
        "metadata": dict(metadata or {}),
    }
    entries: list[dict[str, Any]] = state["entries"]
    entries.append(entry)
    state["entries"] = entries[-MAX_ENTRIES:]
    _save(state)


def show_intelligence_timeline(*, limit: int = 20) -> str:
    state = _load()
    entries = list(reversed(state["entries"][-limit:]))
    if not entries:
        return "Intelligence timeline empty. Run an investigation cycle to populate."
    lines = [f"Intelligence timeline ({len(entries)} recent):"]
    for entry in entries:
        ts = entry.get("timestamp", "")[:19]
        lines.append(
            f"  {ts} [{entry.get('severity', 'info')}] "
            f"{entry.get('category', '?')}: {entry.get('message', '')[:100]}"
        )
    return "\n".join(lines)


def explain_recent_anomalies(*, limit: int = 8) -> str:
    state = _load()
    entries = [
        e
        for e in reversed(state["entries"])
        if e.get("severity") in {"warning", "error", "critical"}
    ][:limit]
    if not entries:
        return "No recent anomalies in intelligence timeline."
    lines = ["Recent anomalies:"]
    for entry in entries:
        ts = entry.get("timestamp", "")[:19]
        lines.append(f"  {ts} {entry.get('category')}: {entry.get('message', '')[:160]}")
        meta = entry.get("metadata") or {}
        action = meta.get("suggested_action")
        if action:
            lines.append(f"    -> {action}")
    return "\n".join(lines)


def compare_today_vs_yesterday_intelligence() -> str:
    state = _load()
    today = datetime.now(timezone.utc).date().isoformat()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in state["entries"]:
        ts = str(entry.get("timestamp", ""))[:10]
        if ts == today:
            buckets["today"].append(entry)
        elif ts == yesterday:
            buckets["yesterday"].append(entry)
    lines = [
        "Intelligence compare today vs yesterday:",
        f"  today ({today}): {len(buckets['today'])} entries",
        f"  yesterday ({yesterday}): {len(buckets['yesterday'])} entries",
    ]
    today_warn = sum(1 for e in buckets["today"] if e.get("severity") in {"warning", "error"})
    yest_warn = sum(1 for e in buckets["yesterday"] if e.get("severity") in {"warning", "error"})
    lines.append(f"  warnings/errors today: {today_warn} vs yesterday: {yest_warn}")
    for label in ("today", "yesterday"):
        if buckets[label]:
            sample = buckets[label][-1]
            lines.append(
                f"  latest {label}: [{sample.get('category')}] {sample.get('message', '')[:80]}"
            )
    return "\n".join(lines)


def write_timeline_report() -> str:
    state = _load()
    try:
        TIMELINE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = TIMELINE_REPORT_DIR / f"{ts}_timeline.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        return str(path)
    except OSError as exc:
        logger.debug("Timeline report skipped: %s", exc)
        return ""
