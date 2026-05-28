"""Contradiction detection for root-cause verification (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.contradiction_engine")

CONTRADICTION_REPORT_DIR = PROJECT_ROOT / "reports" / "causal_analysis"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_contradictions(*, evidence: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from assistant.evidence_collector import collect_evidence_snapshot, get_latest_evidence

    snap = evidence or get_latest_evidence() or collect_evidence_snapshot(source="contradiction_scan")
    blockers = str(snap.get("execution_blockers", "")).lower()
    adapter = str(snap.get("adapter_state", "")).lower()
    flow = str(snap.get("execution_flow", "")).lower()
    risk = str(snap.get("execution_risk", "")).lower()
    stale = str(snap.get("stale_positions", "")).lower()
    contradictions: list[dict[str, Any]] = []

    if ("disabled" in adapter or "disabled" in blockers) and (
        "attempt" in flow and "0 attempt" not in flow and "attempts=0" not in flow
    ):
        contradictions.append(
            {
                "id": "adapter_disabled_vs_attempts",
                "hypothesis_id": "adapter_disabled",
                "message": "Adapter disabled hypothesis contradicted by execution attempt evidence",
                "severity": "warning",
            }
        )

    if "stale" in stale and "none" not in stale and "no stale" in stale:
        contradictions.append(
            {
                "id": "stale_positions_conflict",
                "hypothesis_id": "overlap_stale_positions",
                "message": "Stale positions report contains conflicting none/stale signals",
                "severity": "info",
            }
        )

    if "cap" not in risk and "near" not in risk and "stale telemetry" in blockers:
        contradictions.append(
            {
                "id": "risk_telemetry_conflict",
                "hypothesis_id": "stale_telemetry_risk",
                "message": "Risk telemetry hypothesis lacks supporting risk cap evidence",
                "severity": "info",
            }
        )

    if "last bar" in blockers and "signal" in flow and "accepted" in flow:
        contradictions.append(
            {
                "id": "last_bar_vs_accepted_signals",
                "hypothesis_id": "last_bar_filter",
                "message": "Last-bar gating hypothesis contradicted by accepted signal evidence",
                "severity": "warning",
            }
        )

    return contradictions


def show_contradictory_evidence() -> str:
    items = detect_contradictions()
    if not items:
        return "No contradictory evidence detected in latest snapshot."
    lines = [f"Contradictory evidence ({len(items)}):"]
    for item in items:
        lines.append(f"  - [{item.get('severity', 'info')}] {item.get('hypothesis_id')}: {item.get('message')}")
    return "\n".join(lines)


def explain_contradiction(contradiction_id: str = "") -> str:
    items = detect_contradictions()
    if not items:
        return "No contradictions to explain."
    item = items[0]
    if contradiction_id:
        for candidate in items:
            if candidate.get("id") == contradiction_id or candidate.get("hypothesis_id") == contradiction_id:
                item = candidate
                break
    return (
        f"Contradiction: {item.get('id')}\n"
        f"  hypothesis: {item.get('hypothesis_id')}\n"
        f"  severity: {item.get('severity')}\n"
        f"  detail: {item.get('message')}\n"
        f"  action: re-run verification plan and collect fresh evidence"
    )


def resolve_contradiction(contradiction_id: str = "") -> str:
    """Mark contradiction as reviewed (read-only — no state mutation beyond note)."""
    items = detect_contradictions()
    if not items:
        return "No open contradictions to resolve."
    item = items[0]
    if contradiction_id:
        for candidate in items:
            if candidate.get("id") == contradiction_id or candidate.get("hypothesis_id") == contradiction_id:
                item = candidate
                break
    try:
        CONTRADICTION_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = CONTRADICTION_REPORT_DIR / f"{ts}_resolved_{item.get('id', 'unknown')}.json"
        path.write_text(
            __import__("json").dumps({"resolved_at": _now(), "contradiction": item}, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Contradiction resolve report skipped: %s", exc)
    return (
        f"Contradiction reviewed (read-only): {item.get('id')}\n"
        f"  recommendation: lower causal confidence for {item.get('hypothesis_id')} until re-verified"
    )
