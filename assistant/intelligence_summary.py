"""Operational intelligence summaries (Phase 53)."""

from __future__ import annotations

from assistant.continuity_engine import summarize_unresolved_issues
from assistant.notifications import get_notification_store


def summarize_system_intelligence() -> str:
    sections: list[str] = ["System intelligence summary:"]

    try:
        from runtime.healing_engine import show_runtime_health

        sections.append("\n## Runtime")
        sections.append(show_runtime_health()[:500])
    except Exception as exc:
        sections.append(f"\nRuntime unavailable: {exc}")

    try:
        from operational.unified_state import show_current_state

        sections.append("\n## Current state")
        sections.append(show_current_state()[:500])
    except Exception:
        pass

    try:
        from runtime.background_tasks import get_engine

        sections.append("\n## Background tasks")
        sections.append(get_engine().format_task_list(get_engine().list_running(), title="Running"))
        sections.append(get_engine().format_task_list(get_engine().list_recent_results(limit=3), title="Recent"))
    except Exception as exc:
        sections.append(f"\nTasks unavailable: {exc}")

    notes = get_notification_store().list_notifications(limit=3)
    if notes:
        sections.append("\n## Notifications")
        for note in notes:
            sections.append(f"- [{note.id}] {note.title}: {note.message[:80]}")

    return "\n".join(sections)


def summarize_unresolved_blockers() -> str:
    lines = ["Unresolved blockers:"]
    try:
        from investigation.execution_investigation import rank_execution_block_reasons

        lines.append(rank_execution_block_reasons()[:800])
    except Exception as exc:
        lines.append(f"Execution blockers unavailable: {exc}")
    lines.append("")
    lines.append(summarize_unresolved_issues())
    return "\n".join(lines)


def explain_current_operational_state() -> str:
    sections: list[str] = ["Current operational state:"]
    try:
        from operational.unified_state import show_runtime_summary

        sections.append(show_runtime_summary())
    except Exception:
        pass
    try:
        from operational.trading_operations import summarize_live_engine_status, show_current_execution_risk

        sections.append("\n" + show_current_execution_risk())
        sections.append("\n" + summarize_live_engine_status()[:400])
    except Exception as exc:
        sections.append(f"\nTrading ops unavailable: {exc}")
    try:
        from runtime.dashboard_health import probe_dashboard_health

        probe = probe_dashboard_health()
        sections.append(f"\nDashboard: {probe.get('status', 'unknown')}")
    except Exception:
        pass
    return "\n".join(sections)


def recommend_next_action() -> str:
    suggestions: list[str] = ["Recommended next actions:"]

    try:
        from assistant.hypothesis_engine import _load as load_hypotheses

        active = load_hypotheses().get("active") or []
        if active:
            top = active[0]
            suggestions.append(
                f"- [{top.get('confidence', 0):.2f}] {top.get('title', '')} "
                f"(recurrence={top.get('recurrence', 1)})"
            )
            if top.get("verify_command"):
                suggestions.append(f"  verify: {top['verify_command']}")
    except Exception:
        pass

    try:
        from assistant.investigation_cycles import summarize_autonomous_findings

        findings = summarize_autonomous_findings()
        if "No autonomous investigation cycles" not in findings:
            for line in findings.splitlines()[1:4]:
                if line.strip():
                    suggestions.append(line.strip())
    except Exception:
        pass

    try:
        from assistant.operational_suggestions import show_operational_suggestions

        body = show_operational_suggestions()
        for line in body.splitlines()[1:6]:
            if line.strip():
                suggestions.append(line.strip())
    except Exception:
        pass

    try:
        from runtime.background_tasks import get_engine

        if get_engine().list_failed():
            suggestions.append("- Review failed tasks: show failed tasks")
        if get_engine().list_running():
            suggestions.append("- Monitor active work: show running tasks")
    except Exception:
        pass

    notes = get_notification_store().list_notifications(unread_only=True, limit=1)
    if notes and notes[0].suggested_action:
        suggestions.append(f"- Notification follow-up: {notes[0].suggested_action}")

    if len(suggestions) == 1:
        suggestions.append("- Run investigation cycle")
        suggestions.append("- Show active hypotheses")
        suggestions.append("- Summarize autonomous findings")
    return "\n".join(suggestions)


def what_should_we_investigate_next() -> str:
    lines = ["Investigation priorities:"]
    try:
        from assistant.hypothesis_engine import explain_top_hypothesis, show_active_hypotheses

        lines.append(explain_top_hypothesis()[:700])
        active = show_active_hypotheses()
        if active and "No active hypotheses" not in active:
            lines.append("\nOther active hypotheses:")
            for line in active.splitlines()[1:4]:
                if line.strip():
                    lines.append(line.strip())
    except Exception as exc:
        lines.append(f"Hypothesis engine unavailable: {exc}")

    try:
        from investigation.execution_investigation import explain_top_execution_blocker

        lines.append("\n" + explain_top_execution_blocker()[:500])
    except Exception as exc:
        lines.append(f"\nTop blocker unavailable: {exc}")

    try:
        from assistant.investigation_cycles import summarize_autonomous_findings

        lines.append("\n" + summarize_autonomous_findings()[:500])
    except Exception:
        pass

    try:
        from assistant.continuity_engine import _load

        data = _load()
        if data.get("current_investigation"):
            lines.append(f"\nContinue: {data['current_investigation']}")
        for blocker in (data.get("recent_blockers") or [])[:2]:
            lines.append(f"- unresolved blocker: {blocker}")
    except Exception:
        pass

    lines.append("\nSuggested commands:")
    lines.append("  run investigation cycle")
    lines.append("  show blocker trends")
    lines.append("  show intelligence timeline")
    lines.append("  summarize autonomous findings")
    return "\n".join(lines)
