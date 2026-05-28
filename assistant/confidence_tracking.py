"""Confidence evolution tracking for root causes (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.confidence_tracking")

CONFIDENCE_PATH = DATA_DIR / "confidence_history.json"
CAUSAL_REPORT_DIR = PROJECT_ROOT / "reports" / "causal_analysis"
MAX_POINTS = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"series": {}, "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(CONFIDENCE_PATH, default=_default_state(), validator=_validate)
    if not isinstance(state.get("series"), dict):
        state["series"] = {}
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(CONFIDENCE_PATH, state)
    try:
        CAUSAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = CAUSAL_REPORT_DIR / f"{ts}_confidence.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Confidence report skipped: %s", exc)


def record_confidence_point(
    root_cause_id: str,
    *,
    confidence: float,
    causal_score: float,
    evidence_count: int,
    recurrence: int,
    contradictory_count: int = 0,
    verification_status: str = "pending",
) -> None:
    state = _load()
    series: dict[str, list] = state["series"]
    points = series.setdefault(root_cause_id, [])
    points.append(
        {
            "timestamp": _now(),
            "confidence": round(max(0.0, min(confidence, 1.0)), 3),
            "causal_score": round(max(0.0, min(causal_score, 1.0)), 3),
            "evidence_count": evidence_count,
            "recurrence": recurrence,
            "contradictory_count": contradictory_count,
            "verification_status": verification_status,
        }
    )
    series[root_cause_id] = points[-MAX_POINTS:]
    _save(state)


def show_confidence_evolution(*, limit: int = 5) -> str:
    state = _load()
    series: dict[str, list] = state.get("series") or {}
    if not series:
        return "No confidence evolution recorded yet. Run verify root causes first."
    lines = ["Confidence evolution:"]
    for root_id, points in list(series.items())[:limit]:
        if not points:
            continue
        latest = points[-1]
        earliest = points[0]
        delta = latest.get("causal_score", 0) - earliest.get("causal_score", 0)
        lines.append(
            f"  - {root_id}: causal={latest.get('causal_score', 0):.2f} "
            f"(delta {delta:+.2f}) status={latest.get('verification_status', 'pending')} "
            f"points={len(points)}"
        )
    return "\n".join(lines)


def explain_confidence_changes(root_cause_id: str = "") -> str:
    state = _load()
    series: dict[str, list] = state.get("series") or {}
    if not series:
        return "No confidence history available."
    rid = root_cause_id or next(iter(series))
    points = series.get(rid) or []
    if len(points) < 2:
        return f"Insufficient history for {rid}."
    first, last = points[0], points[-1]
    lines = [
        f"Confidence changes for {rid}:",
        f"  causal score: {first.get('causal_score', 0):.2f} -> {last.get('causal_score', 0):.2f}",
        f"  confidence: {first.get('confidence', 0):.2f} -> {last.get('confidence', 0):.2f}",
        f"  evidence: {first.get('evidence_count', 0)} -> {last.get('evidence_count', 0)}",
        f"  recurrence: {first.get('recurrence', 0)} -> {last.get('recurrence', 0)}",
        f"  contradictions: {first.get('contradictory_count', 0)} -> {last.get('contradictory_count', 0)}",
        f"  verification: {first.get('verification_status', 'pending')} -> {last.get('verification_status', 'pending')}",
    ]
    if last.get("contradictory_count", 0) > first.get("contradictory_count", 0):
        lines.append("  trend: contradictions increased — causal confidence capped")
    elif last.get("causal_score", 0) > first.get("causal_score", 0):
        lines.append("  trend: causal convergence improving")
    else:
        lines.append("  trend: stable or declining causal support")
    return "\n".join(lines)


def compare_root_cause_confidence() -> str:
    state = _load()
    series: dict[str, list] = state.get("series") or {}
    if not series:
        return "No root cause confidence data to compare."
    ranked: list[tuple[str, float, int]] = []
    for rid, points in series.items():
        if not points:
            continue
        latest = points[-1]
        ranked.append((rid, float(latest.get("causal_score", 0)), len(points)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    lines = ["Root cause confidence ranking:"]
    for idx, (rid, score, count) in enumerate(ranked[:8], start=1):
        lines.append(f"  {idx}. {rid}: causal_score={score:.2f} ({count} points)")
    return "\n".join(lines)
