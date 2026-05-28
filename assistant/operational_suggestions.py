"""Smart operational suggestions 2.0 (Phase 51)."""

from __future__ import annotations

from typing import Any

from config import PROJECT_ROOT

SUGGESTIONS_REPORT_DIR = PROJECT_ROOT / "reports" / "context_memory"

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _severity(item: dict[str, Any]) -> str:
    return str(item.get("severity") or item.get("risk") or "info")


def build_operational_suggestions() -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    def _add(item: dict[str, Any]) -> None:
        key = item.get("title", "").lower().strip()
        if not key or key in seen_titles:
            return
        seen_titles.add(key)
        suggestions.append(item)

    try:
        from runtime.healing_engine import collect_runtime_health

        health = collect_runtime_health()
        for check in health.get("checks", []):
            if check.get("ok"):
                continue
            name = check.get("name", "subsystem")
            detail = check.get("detail", "")
            sev = "low"
            cmd = f"show runtime health"
            if name == "dashboard":
                sev = "low" if detail.startswith("status=starting") else "medium"
                cmd = "restart dashboard confirm"
            elif name in {"overlay", "tts_worker"}:
                sev = "medium"
                cmd = f"recover {name.replace('_worker', '')} confirm"
            elif name == "operator_console":
                sev = "medium"
                cmd = "show stuck workers"
            _add(
                {
                    "title": f"{name} degraded",
                    "severity": sev,
                    "evidence": detail,
                    "evidence_source": "runtime.healing_engine.collect_runtime_health",
                    "action": cmd,
                    "risk": sev,
                }
            )
    except Exception as exc:
        _add(
            {
                "title": "runtime health unavailable",
                "severity": "info",
                "evidence": str(exc),
                "evidence_source": "runtime.healing_engine",
                "action": "foundation health check",
                "risk": "info",
            }
        )

    try:
        from vision.screen_system import probe_screen_system

        screen = probe_screen_system()
        if not screen.get("screenshot_capability"):
            _add(
                {
                    "title": "screen capture degraded",
                    "severity": "medium",
                    "evidence": "mss/pygetwindow missing",
                    "evidence_source": "vision.screen_system.probe_screen_system",
                    "action": "show screen system status",
                    "risk": "medium",
                }
            )
    except Exception:
        pass

    try:
        from investigation.execution_cleanup import show_stale_open_positions

        stale = show_stale_open_positions()
        if "none" not in stale.lower() and "0" not in stale:
            _add(
                {
                    "title": "stale open positions detected",
                    "severity": "medium",
                    "evidence": stale[:200],
                    "evidence_source": "investigation.execution_cleanup",
                    "action": "show stale open positions",
                    "risk": "medium",
                }
            )
    except Exception:
        pass

    try:
        from investigation.execution_investigation import show_execution_blockers

        blockers = show_execution_blockers()
        if "none" not in blockers.lower():
            _add(
                {
                    "title": "execution blockers present",
                    "severity": "high",
                    "evidence": blockers[:200],
                    "evidence_source": "investigation.execution_investigation",
                    "action": "show top operational blockers",
                    "risk": "high",
                }
            )
    except Exception:
        pass

    suggestions.sort(key=lambda x: _SEVERITY_RANK.get(_severity(x), 99))
    return suggestions[:12]


def show_operational_suggestions() -> str:
    items = build_operational_suggestions()
    if not items:
        return "Operational suggestions: none — systems look stable."
    lines = ["Operational suggestions (ranked, deduplicated, not auto-applied):"]
    for item in items:
        sev = _severity(item)
        lines.append(f"  - {item['title']} [{sev}]")
        lines.append(f"      evidence: {item.get('evidence', '')[:120]}")
        lines.append(f"      source: {item.get('evidence_source', 'local')}")
        lines.append(f"      try: {item.get('action', '')}")
    return "\n".join(lines)
