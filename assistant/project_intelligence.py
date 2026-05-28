"""Project intelligence layer for conversational engineering assistant (Phase 56)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import load_json

logger = setup_logger("jarvis.assistant.project_intelligence")

PROJECT_INDEX_PATH = DATA_DIR / "project_index.json"


def _active_project_root() -> Path:
    return PROJECT_ROOT


def _load_index() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    return load_json(PROJECT_INDEX_PATH, default={}, validator=_validate)


def _recent_reports(limit: int = 5) -> list[str]:
    reports: list[str] = []
    for sub in ("autonomous_investigations", "assistant_state", "notifications"):
        root = PROJECT_ROOT / "reports" / sub
        if not root.is_dir():
            continue
        for path in sorted(root.glob("**/*"), reverse=True)[:limit]:
            if path.is_file():
                reports.append(str(path.relative_to(PROJECT_ROOT))[:120])
        if len(reports) >= limit:
            break
    return reports[:limit]


def _runtime_blockers() -> list[str]:
    lines: list[str] = []
    try:
        from assistant.intelligence_summary import summarize_unresolved_blockers

        body = summarize_unresolved_blockers()
        for line in body.splitlines():
            if line.strip().startswith("-") or "blocker" in line.lower():
                lines.append(line.strip()[:120])
    except Exception:
        pass
    return lines[:5]


def explain_this_project() -> str:
    root = _active_project_root()
    index = _load_index()
    lines = [
        "Project overview:",
        f"  root: {root}",
        f"  indexed entries: {len(index.get('entries') or index) if isinstance(index, dict) else 0}",
    ]
    try:
        from phase45_investigation import inspect_project, summarize_current_project

        summary = summarize_current_project()
        if summary:
            lines.append(summary[:600])
        detail = inspect_project()
        if detail and detail not in (summary or ""):
            lines.append(detail[:400])
    except Exception:
        lines.append("  (project summary unavailable)")
    blockers = _runtime_blockers()
    if blockers:
        lines.append("  current blockers:")
        lines.extend(f"    {b}" for b in blockers[:3])
    return "\n".join(lines)


def explain_architecture() -> str:
    lines = [
        "Architecture snapshot:",
        "  voice: wake/stream STT -> router -> actions -> TTS (streaming + verified backend)",
        "  brain: rules/grammar -> hybrid understanding -> registry execution",
        "  assistant: investigations, root causes, proactive monitor, conversation state",
        "  runtime: background tasks, healing, observability, overlay HUD",
        "  data: persistent JSON under data/ + reports/",
    ]
    try:
        from assistant.investigation_graph import show_investigation_graph

        graph = show_investigation_graph()
        if graph and "nodes" in graph.lower():
            lines.append("")
            lines.append(graph[:600])
    except Exception:
        pass
    return "\n".join(lines)


def prepare_investor_summary() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"Investor summary draft ({ts}):",
        "  Product: JARVIS autonomous engineering assistant with voice, investigations, and trading ops.",
        "  Capability: continuous monitoring, root-cause verification, explainable recommendations.",
        "  Safety: read-only investigations by default; patch proposals require confirmation.",
    ]
    try:
        from assistant.root_cause_summary import summarize_verified_findings

        findings = summarize_verified_findings()
        if findings:
            lines.append("")
            lines.append(findings[:700])
    except Exception:
        pass
    blockers = _runtime_blockers()
    if blockers:
        lines.append("")
        lines.append("  Known operational blockers:")
        lines.extend(f"    {b}" for b in blockers[:3])
    return "\n".join(lines)


def generate_project_roadmap() -> str:
    reports = _recent_reports()
    lines = [
        "Project roadmap (suggested next milestones):",
        "  1. Stabilize real-time conversational runtime (Phase 56)",
        "  2. Reduce voice latency and improve barge-in/resume",
        "  3. Expand project intelligence and autonomous patch validation",
        "  4. Harden reliability (queues, watchdogs, recovery)",
    ]
    if reports:
        lines.append("  recent artifacts:")
        lines.extend(f"    - {r}" for r in reports[:4])
    blockers = _runtime_blockers()
    if blockers:
        lines.append("  unblock first:")
        lines.extend(f"    - {b}" for b in blockers[:2])
    return "\n".join(lines)


def show_project_intelligence() -> str:
    return "\n\n".join(
        [
            explain_this_project(),
            explain_architecture(),
            f"Recent changes:\n  try: what changed since last session",
            generate_project_roadmap(),
        ]
    )


def get_overlay_snapshot() -> dict[str, Any]:
    index = _load_index()
    return {
        "project_root": str(_active_project_root())[:60],
        "indexed": len(index) if isinstance(index, dict) else 0,
        "blockers": len(_runtime_blockers()),
    }
