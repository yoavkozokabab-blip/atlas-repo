"""Unified operational state views (Phase 50)."""

from __future__ import annotations

from reliability.jarvis_status import build_jarvis_status_report
from runtime.healing_engine import collect_runtime_health, show_runtime_health


def show_current_state() -> str:
    health = collect_runtime_health()
    lines = [
        "Current JARVIS state:",
        f"  runtime health: {health['overall']}",
        f"  active checks: {len(health.get('checks', []))}",
    ]
    try:
        from memory.task_memory import what_was_i_doing

        lines.append("")
        lines.append(what_was_i_doing())
    except Exception:
        pass
    return "\n".join(lines)


def show_active_systems() -> str:
    snap = collect_runtime_health().get("snapshot", {})
    lines = ["Active systems:"]
    for name, detail in snap.items():
        if isinstance(detail, dict) and "error" not in detail:
            lines.append(f"  - {name}: ok")
        elif isinstance(detail, dict):
            lines.append(f"  - {name}: degraded ({detail.get('error', '')[:60]})")
        else:
            lines.append(f"  - {name}: {detail}")
    return "\n".join(lines)


def show_runtime_summary() -> str:
    parts = [show_runtime_health(), "", "Status center:", build_jarvis_status_report()[:1500]]
    return "\n".join(parts)


def phase50_status() -> str:
    return "\n".join(
        [
            "Phase 50 — Computer Control + Context Memory",
            "  desktop: open/focus apps, reports, screenshots (allowlisted)",
            "  context: what am I looking at, summarize screen, continue investigation",
            "  memory: what was I doing, resume last task, recent investigations",
            "  trading ops: summarize trading health, execution blockers, live engine status",
            "  suggestions: show operational suggestions",
            "  unified: show current state, show active systems, show runtime summary",
        ]
    )
