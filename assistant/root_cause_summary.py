"""Root cause summaries and operational failure explanations (Phase 55)."""

from __future__ import annotations

from assistant.confidence_tracking import compare_root_cause_confidence, show_confidence_evolution
from assistant.contradiction_engine import show_contradictory_evidence
from assistant.root_cause_engine import get_dominant_root_cause, sync_root_causes


def summarize_root_causes() -> str:
    candidates = sync_root_causes()
    if not candidates:
        return "No root cause candidates identified yet."
    lines = [f"Root cause summary ({len(candidates)} candidates):"]
    for idx, candidate in enumerate(candidates[:5], start=1):
        lines.append(
            f"  {idx}. [{candidate.get('causal_score', 0):.2f}] {candidate.get('hypothesis', '')} "
            f"status={candidate.get('verification_status', 'pending')} "
            f"recurrence={candidate.get('recurrence_count', 1)} "
            f"evidence={candidate.get('evidence_count', 0)}"
        )
    lines.append("")
    lines.append(show_confidence_evolution(limit=3))
    return "\n".join(lines)


def explain_dominant_root_cause() -> str:
    dominant = get_dominant_root_cause() or {}
    if not dominant:
        dominant = (sync_root_causes() or [None])[0] or {}
    if not dominant:
        return "No dominant root cause identified."
    lines = [
        f"Dominant root cause: {dominant.get('hypothesis', '')}",
        f"  causal score: {dominant.get('causal_score', 0):.2f}",
        f"  confidence: {dominant.get('confidence', 0):.2f}",
        f"  verification: {dominant.get('verification_status', 'pending')}",
        f"  recurrence: {dominant.get('recurrence_count', 1)}",
        f"  evidence count: {dominant.get('evidence_count', 0)}",
        f"  trend: {dominant.get('historical_trend', 'stable')}",
        f"  next experiment: {dominant.get('recommended_next_experiment', 'n/a')}",
    ]
    contradictions = dominant.get("contradictory_evidence") or []
    if contradictions:
        lines.append("  contradictions:")
        for item in contradictions[:3]:
            lines.append(f"    - {item}")
    return "\n".join(lines)


def explain_operational_failures() -> str:
    sections = ["Operational failure analysis:"]
    sections.append(explain_dominant_root_cause())
    sections.append("")
    try:
        from investigation.execution_investigation import explain_top_execution_blocker

        sections.append(explain_top_execution_blocker()[:600])
    except Exception as exc:
        sections.append(f"Top blocker unavailable: {exc}")
    sections.append("")
    sections.append(show_contradictory_evidence())
    return "\n".join(sections)


def summarize_verified_findings() -> str:
    candidates = sync_root_causes()
    verified = [c for c in candidates if c.get("verification_status") == "verified"]
    partial = [c for c in candidates if c.get("verification_status") == "partial"]
    lines = [
        f"Verified findings: {len(verified)} verified, {len(partial)} partial, "
        f"{len(candidates) - len(verified) - len(partial)} pending",
    ]
    for candidate in verified[:5]:
        lines.append(
            f"  - {candidate.get('hypothesis', '')} "
            f"(causal={candidate.get('causal_score', 0):.2f}, evidence={candidate.get('evidence_count', 0)})"
        )
    if not verified:
        lines.append("  No fully verified root causes yet — run verify root causes.")
    lines.append("")
    lines.append(compare_root_cause_confidence())
    return "\n".join(lines)


def explain_why_trades_are_blocked() -> str:
    lines = ["Why trades are blocked:"]
    try:
        from investigation.execution_investigation import (
            explain_top_execution_blocker,
            rank_execution_block_reasons,
        )

        lines.append(explain_top_execution_blocker()[:500])
        lines.append("")
        lines.append(rank_execution_block_reasons()[:500])
    except Exception as exc:
        lines.append(f"Execution blockers unavailable: {exc}")
    dominant = get_dominant_root_cause()
    if dominant:
        lines.append("")
        lines.append(
            f"Verified root-cause context: {dominant.get('hypothesis', '')} "
            f"(causal={dominant.get('causal_score', 0):.2f}, "
            f"status={dominant.get('verification_status', 'pending')})"
        )
    return "\n".join(lines)
