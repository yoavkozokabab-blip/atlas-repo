"""Local-only product analytics for JARVIS Desktop (no cloud, no accounts)."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List


def analytics_data_dir() -> str:
    override = os.environ.get("JARVIS_DESKTOP_DATA", "").strip()
    if override:
        return os.path.abspath(override)
    return os.path.join(os.path.expanduser("~"), ".jarvis_desktop")


def analytics_file_path() -> str:
    return os.path.join(analytics_data_dir(), "analytics.jsonl")


def track_event(event: str, **properties: Any) -> Dict[str, Any]:
    """Append one analytics row to the local JSONL file."""
    name = (event or "").strip()
    if not name:
        return {"ok": False, "error": "Event name required."}
    os.makedirs(analytics_data_dir(), exist_ok=True)
    row = {
        "ts": time.time(),
        "event": name,
        **{k: v for k, v in properties.items() if v is not None},
    }
    with open(analytics_file_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "event": name, "path": analytics_file_path()}


def _read_events() -> List[Dict[str, Any]]:
    path = analytics_file_path()
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def analytics_summary() -> Dict[str, Any]:
    events = _read_events()
    counts: Dict[str, int] = {}
    for row in events:
        key = str(row.get("event", "unknown"))
        counts[key] = counts.get(key, 0) + 1
    return {
        "ok": True,
        "local_only": True,
        "path": analytics_file_path(),
        "total_events": len(events),
        "counts": counts,
        "scans_completed": counts.get("scan_completed", 0),
        "graph_opens": counts.get("graph_opened", 0),
        "copilot_questions": counts.get("copilot_question", 0),
        "exports": counts.get("export_created", 0) + counts.get("bundle_exported", 0),
    }


def reset_analytics_for_tests() -> None:
    path = analytics_file_path()
    if os.path.isfile(path):
        os.remove(path)
