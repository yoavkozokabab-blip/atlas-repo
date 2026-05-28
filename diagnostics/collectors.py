"""Read-only data collectors for diagnostics (no side effects)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from actions.log_utils import (
    ERROR_KEYWORDS,
    REJECTION_REASONS,
    aggregate_reason_counts,
    iter_recent_log_files,
    lines_matching,
    read_tail,
)
from actions.trading_dashboard import _fetch_json, _port_open
from config import (
    DASHBOARD_HEALTH_URL,
    DASHBOARD_SUMMARY_URL,
    VISION_ENABLED,
)
from core.runtime_state import get_runtime_state


def collect_dashboard() -> dict[str, Any]:
    port_up = _port_open("127.0.0.1", 8077)
    health = _fetch_json(DASHBOARD_HEALTH_URL)
    summary = _fetch_json(DASHBOARD_SUMMARY_URL)
    reachable = health is not None or port_up
    kill_switch = None
    execution_mode = None
    for blob in (health, summary):
        if not blob:
            continue
        for key in ("kill_switch", "killSwitch"):
            if key in blob:
                kill_switch = blob[key]
        for key in ("execution_mode", "mode"):
            if key in blob:
                execution_mode = blob[key]
    return {
        "reachable": reachable,
        "port_open": port_up,
        "health": health,
        "summary": summary,
        "kill_switch": kill_switch,
        "execution_mode": execution_mode,
    }


def collect_log_errors(*, max_files: int = 8) -> dict[str, Any]:
    all_lines: list[str] = []
    sources: list[str] = []
    for path in iter_recent_log_files(max_files=max_files):
        lines = read_tail(path, max_lines=400)
        hits = lines_matching(lines, ERROR_KEYWORDS)
        if hits:
            sources.append(path.name)
            all_lines.extend(f"[{path.name}] {ln}" for ln in hits[-10:])
    return {
        "lines": all_lines[-30:],
        "line_count": len(all_lines),
        "sources": sources[:5],
    }


def collect_rejections() -> dict[str, Any]:
    combined: Counter[str] = Counter()
    samples: list[str] = []
    for path in iter_recent_log_files(max_files=6):
        lines = read_tail(path, max_lines=500)
        combined.update(aggregate_reason_counts(lines))
        for reason in REJECTION_REASONS:
            for ln in lines:
                if reason in ln.lower():
                    samples.append(f"{path.name}: {ln.strip()[:120]}")
                    break
    top = combined.most_common(8)
    return {
        "counts": dict(combined),
        "top_reasons": top,
        "samples": samples[:8],
        "total_hits": sum(combined.values()),
    }


def collect_runtime() -> dict[str, Any]:
    state = get_runtime_state()
    out = {
        "running": state.running,
        "voice_enabled": state.voice_enabled,
        "speak_enabled": state.speak_enabled,
        "tray_enabled": state.tray_enabled,
        "last_result_summary": state.last_result_summary,
        "last_error": state.last_error,
    }
    try:
        from services.observability import get_observability

        snap = get_observability().snapshot()
        out["observability_failure_count"] = len(snap.get("failures", {}))
        out["observability_trace_count"] = len(snap.get("traces", []))
    except Exception:
        pass
    return out


def collect_loop_signals() -> dict[str, Any]:
    loop_pat = (
        "live loop",
        "daily loop",
        "weekly loop",
        "run_live",
        "scheduled",
        "kill_switch",
        "stopped",
        "started",
    )
    hits: list[str] = []
    for path in iter_recent_log_files(max_files=6):
        for line in read_tail(path, max_lines=300):
            lower = line.lower()
            if any(p in lower for p in loop_pat):
                hits.append(f"[{path.name}] {line.strip()[:140]}")
        if len(hits) >= 20:
            break
    return {"lines": hits[:20], "line_count": len(hits)}


def collect_screen_errors() -> dict[str, Any]:
    if not VISION_ENABLED:
        return {
            "enabled": False,
            "matches": [],
            "match_count": 0,
            "note": "Vision disabled (VISION_ENABLED=false).",
        }
    try:
        from vision.screen_analyzer import detect_screen_errors

        data = detect_screen_errors()
        return {
            "enabled": True,
            "matches": data.get("matches", [])[:15],
            "match_count": data.get("match_count", 0),
            "ocr_error": data.get("ocr_error"),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "matches": [],
            "match_count": 0,
            "error": str(exc),
        }
