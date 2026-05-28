"""Root cause verification engine (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.root_cause_engine")

ROOT_CAUSES_PATH = DATA_DIR / "root_causes.json"
ROOT_CAUSE_REPORT_DIR = PROJECT_ROOT / "reports" / "root_cause_engine"
MAX_HISTORY = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"candidates": [], "history": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(ROOT_CAUSES_PATH, default=_default_state(), validator=_validate)
    state.setdefault("candidates", [])
    state.setdefault("history", [])
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(ROOT_CAUSES_PATH, state)
    try:
        ROOT_CAUSE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = ROOT_CAUSE_REPORT_DIR / f"{ts}_root_causes.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Root cause report skipped: %s", exc)


def _compute_causal_score(
    *,
    confidence: float,
    evidence_count: int,
    recurrence: int,
    contradictory_count: int,
    verification_status: str,
) -> float:
    support = min(1.0, (evidence_count * 0.12) + (recurrence * 0.04))
    raw = min(confidence, support)
    raw -= contradictory_count * 0.15
    if verification_status == "verified":
        raw = min(1.0, raw + 0.08)
    elif verification_status == "contradicted":
        raw = min(raw, 0.35)
    return round(max(0.0, min(raw, 0.95)), 3)


def sync_root_causes() -> list[dict[str, Any]]:
    from assistant.contradiction_engine import detect_contradictions
    from assistant.evidence_collector import collect_evidence_snapshot, get_evidence_for_hypothesis
    from assistant.hypothesis_engine import refresh_hypotheses
    from assistant.verification_plans import generate_verification_plans

    hypotheses = refresh_hypotheses()
    plans = {p.get("hypothesis_id"): p for p in generate_verification_plans()}
    evidence = collect_evidence_snapshot(source="root_cause_sync")
    contradictions = detect_contradictions(evidence=evidence)
    contradiction_by_hyp: dict[str, int] = {}
    for item in contradictions:
        hid = str(item.get("hypothesis_id", ""))
        contradiction_by_hyp[hid] = contradiction_by_hyp.get(hid, 0) + 1

    state = _load()
    prev = {c.get("id"): c for c in state.get("candidates", []) if isinstance(c, dict)}
    candidates: list[dict[str, Any]] = []
    now = _now()

    for hyp in hypotheses:
        hid = str(hyp.get("id", ""))
        if not hid:
            continue
        evidence_items = get_evidence_for_hypothesis(hid)
        evidence_items.extend([str(x) for x in hyp.get("evidence") or []][:4])
        evidence_items = list(dict.fromkeys(evidence_items))[:10]
        plan = plans.get(hid, {})
        verification_status = str(plan.get("status", "pending"))
        contradictory = contradiction_by_hyp.get(hid, 0)
        if contradictory and verification_status == "verified":
            verification_status = "contradicted"
        recurrence = int(hyp.get("recurrence", 1))
        confidence = float(hyp.get("confidence", 0))
        evidence_count = len(evidence_items)
        causal_score = _compute_causal_score(
            confidence=confidence,
            evidence_count=evidence_count,
            recurrence=recurrence,
            contradictory_count=contradictory,
            verification_status=verification_status,
        )
        capped_confidence = min(confidence, causal_score + 0.1)
        old = prev.get(hid, {})
        trend = "stable"
        if causal_score > float(old.get("causal_score", 0)):
            trend = "rising"
        elif causal_score < float(old.get("causal_score", 0)):
            trend = "falling"
        candidate = {
            "id": hid,
            "hypothesis": hyp.get("title", hid),
            "confidence": round(capped_confidence, 3),
            "evidence_count": evidence_count,
            "recurrence_count": recurrence,
            "causal_score": causal_score,
            "contradictory_evidence": [
                c.get("message", "") for c in contradictions if c.get("hypothesis_id") == hid
            ],
            "verification_status": verification_status,
            "historical_trend": trend,
            "related_reports": list(hyp.get("related_reports") or [])[:5],
            "recommended_next_experiment": _recommended_experiment(hid),
            "updated_at": now,
        }
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.get("causal_score", 0), reverse=True)
    state["candidates"] = candidates
    history: list[dict[str, Any]] = state.get("history", [])
    history.extend(candidates)
    state["history"] = history[-MAX_HISTORY:]
    _save(state)

    from assistant.confidence_tracking import record_confidence_point

    for candidate in candidates:
        record_confidence_point(
            candidate["id"],
            confidence=candidate["confidence"],
            causal_score=candidate["causal_score"],
            evidence_count=candidate["evidence_count"],
            recurrence=candidate["recurrence_count"],
            contradictory_count=len(candidate.get("contradictory_evidence") or []),
            verification_status=candidate["verification_status"],
        )
    return candidates


def _recommended_experiment(hypothesis_id: str) -> str:
    mapping = {
        "adapter_disabled": "simulate unblock scenario",
        "overlap_stale_positions": "simulate execution cleanup patch",
        "last_bar_filter": "rank dead signal causes",
        "stale_telemetry_risk": "compare risk before after cleanup",
        "cluster_divergence": "cluster replay divergences",
    }
    return mapping.get(hypothesis_id, "run investigation cycle")


def verify_root_causes() -> dict[str, Any]:
    from assistant.verification_plans import run_verification_plan

    candidates = sync_root_causes()
    results: list[dict[str, Any]] = []
    for candidate in candidates[:3]:
        payload = run_verification_plan(str(candidate.get("id", "")))
        results.append(payload)
    sync_root_causes()
    return {"verified": len(results), "results": results, "top": candidates[0] if candidates else None}


def verify_root_causes_now() -> str:
    payload = verify_root_causes()
    top = payload.get("top") or {}
    lines = [
        f"Root cause verification complete ({payload.get('verified', 0)} plans run).",
    ]
    if top:
        lines.append(
            f"  top: {top.get('hypothesis', '')} "
            f"causal={top.get('causal_score', 0):.2f} status={top.get('verification_status', 'pending')}"
        )
    for result in payload.get("results") or []:
        lines.append(f"  - {result.get('hypothesis_id')}: {result.get('status')}")
    return "\n".join(lines)


def get_dominant_root_cause() -> dict[str, Any] | None:
    candidates = _load().get("candidates") or []
    return candidates[0] if candidates else None


def get_overlay_snapshot() -> dict[str, Any]:
    """Lightweight overlay snapshot from persisted root cause state."""
    dominant = get_dominant_root_cause() or {}
    from assistant.confidence_tracking import _load as load_confidence

    trend = "stable"
    series = (load_confidence().get("series") or {}).get(str(dominant.get("id", "")), [])
    if len(series) >= 2:
        delta = series[-1].get("causal_score", 0) - series[-2].get("causal_score", 0)
        trend = "rising" if delta > 0.02 else "falling" if delta < -0.02 else "stable"
    contradictory = dominant.get("contradictory_evidence") or []
    return {
        "dominant_root_cause": str(dominant.get("hypothesis", ""))[:100],
        "causal_score": dominant.get("causal_score", 0),
        "confidence_trend": trend,
        "active_contradictions": len(contradictory),
        "verification_status": dominant.get("verification_status", "pending"),
        "recommended_verification": str(dominant.get("recommended_next_experiment", ""))[:80],
    }
