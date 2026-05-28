"""Rules-based planning output (no LLM, no execution)."""

from __future__ import annotations

from pathlib import Path

from core.session import SessionState
from operating.workspace_context import get_cached_mode


def build_plan_report(goal: str = "") -> str:
    session = SessionState.load()
    mode = get_cached_mode() or session.activity_mode or "idle"
    goal_line = goal.strip() or session.last_intent or "current task"
    proj = Path(session.current_project_root or ".").name

    lines = [
        f"# Plan: {goal_line}",
        "",
        f"**Context:** workspace mode `{mode}`, project `{proj}`",
        "",
        "## Phase 1 — Understand (read-only)",
        "- what am i doing",
        "- run diagnostics",
        "- summarize recent changes",
        "",
        "## Phase 2 — Investigate",
        "- explain this error / explain last failure",
        "- show failing tests",
        "- search project knowledge",
        "",
        "## Phase 3 — Change (supervised only)",
        "- start task → approve task plan → propose task patch",
        "- approve task patch → apply task patch (confirmation required)",
        "",
        "## Risks",
        "- Patches and live trading require explicit confirmation.",
        "- Git/pytest helpers are read-only in Phase 40.",
        "",
        "## Files likely touched",
        f"- Project root: `{session.current_project_root or 'n/a'}`",
        "- Check last_opened_file in session for editor context",
        "",
        "## Suggested tests",
        "- show failing tests",
        "- run jarvis health check",
        "",
        "---",
        "**No auto-execution.** Speak each command; JARVIS will route through security and registry.",
    ]
    return "\n".join(lines)
