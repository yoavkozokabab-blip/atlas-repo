"""Autonomous hypothesis engine (Phase 54)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.hypothesis_engine")

HYPOTHESES_PATH = DATA_DIR / "hypotheses.json"
HYPOTHESIS_REPORT_DIR = PROJECT_ROOT / "reports" / "hypothesis_engine"
MAX_HISTORY = 100


@dataclass
class Hypothesis:
    id: str
    title: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    related_reports: list[str] = field(default_factory=list)
    verify_command: str = ""
    recurrence: int = 1
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"active": [], "history": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(HYPOTHESES_PATH, default=_default_state(), validator=_validate)
    state.setdefault("active", [])
    state.setdefault("history", [])
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(HYPOTHESES_PATH, state)


def _gather_signals() -> list[Hypothesis]:
    hypotheses: list[Hypothesis] = []
    now = _now()

    try:
        from investigation.execution_cleanup import show_stale_open_positions

        stale = show_stale_open_positions()
        if "stale" in stale.lower():
            hypotheses.append(
                Hypothesis(
                    id="overlap_stale_positions",
                    title="Overlap block caused by stale open_positions state",
                    confidence=0.82,
                    evidence=[stale.splitlines()[0][:160]],
                    verify_command="show stale open positions",
                    created_at=now,
                    updated_at=now,
                )
            )
    except Exception:
        pass

    try:
        from investigation.execution_investigation import show_execution_blockers

        blockers = show_execution_blockers()
        lower = blockers.lower()
        if "disabled" in lower or "adapter" in lower:
            hypotheses.append(
                Hypothesis(
                    id="adapter_disabled",
                    title="Adapter disabled causing execution attempts=0",
                    confidence=0.88,
                    evidence=[blockers.splitlines()[0][:160]],
                    verify_command="inspect execution adapter",
                    created_at=now,
                    updated_at=now,
                )
            )
        if "last bar" in lower:
            hypotheses.append(
                Hypothesis(
                    id="last_bar_filter",
                    title="Last-bar filtering suppressing entries",
                    confidence=0.74,
                    evidence=[line[:160] for line in blockers.splitlines()[:2]],
                    verify_command="reconstruct execution flow",
                    created_at=now,
                    updated_at=now,
                )
            )
    except Exception:
        pass

    try:
        from operational.trading_operations import show_current_execution_risk

        risk = show_current_execution_risk()
        if "cap" in risk.lower() or "near" in risk.lower() or "stale" in risk.lower():
            hypotheses.append(
                Hypothesis(
                    id="stale_telemetry_risk",
                    title="Stale execution telemetry inflating open risk",
                    confidence=0.7,
                    evidence=[risk.splitlines()[0][:160]],
                    verify_command="show current execution risk",
                    created_at=now,
                    updated_at=now,
                )
            )
    except Exception:
        pass

    try:
        from investigation.divergence_clustering import show_divergence_clusters

        if "cluster" in show_divergence_clusters().lower():
            hypotheses.append(
                Hypothesis(
                    id="cluster_divergence",
                    title="Replay divergences cluster around systemic mismatch pattern",
                    confidence=0.68,
                    evidence=["see divergence clusters report"],
                    verify_command="explain largest divergence cluster",
                    created_at=now,
                    updated_at=now,
                )
            )
    except Exception:
        pass

    hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    return hypotheses[:8]


def refresh_hypotheses() -> list[dict[str, Any]]:
    incoming = _gather_signals()
    state = _load()
    prev_active = {h.get("id"): h for h in state.get("active", []) if isinstance(h, dict)}
    merged: list[dict[str, Any]] = []
    for hyp in incoming:
        payload = hyp.to_dict()
        old = prev_active.get(hyp.id)
        if old:
            payload["recurrence"] = int(old.get("recurrence", 1)) + 1
        merged.append(payload)
    state["active"] = merged
    history: list[dict[str, Any]] = state.get("history", [])
    history.extend(merged)
    state["history"] = history[-MAX_HISTORY:]
    _save(state)
    try:
        HYPOTHESIS_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = HYPOTHESIS_REPORT_DIR / f"{ts}_hypotheses.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Hypothesis report skipped: %s", exc)
    return merged


def show_active_hypotheses() -> str:
    state = _load()
    active = state.get("active") or []
    if not active:
        active = refresh_hypotheses()
    if not active:
        return "No active hypotheses generated yet."
    lines = [f"Active hypotheses ({len(active)}):"]
    for idx, hyp in enumerate(active, start=1):
        lines.append(
            f"  {idx}. [{hyp.get('confidence', 0):.2f}] {hyp.get('title', '')} "
            f"(recurrence={hyp.get('recurrence', 1)})"
        )
        lines.append(f"       verify: {hyp.get('verify_command', 'n/a')}")
    return "\n".join(lines)


def explain_top_hypothesis() -> str:
    state = _load()
    active = state.get("active") or refresh_hypotheses()
    if not active:
        return "No hypotheses available."
    top = active[0]
    lines = [
        f"Top hypothesis: {top.get('title', '')}",
        f"  confidence: {top.get('confidence', 0):.2f}",
        f"  recurrence: {top.get('recurrence', 1)}",
        f"  verify: {top.get('verify_command', 'n/a')}",
        "  evidence:",
    ]
    for item in top.get("evidence", [])[:6]:
        lines.append(f"    - {item}")
    return "\n".join(lines)


def verify_active_hypotheses() -> str:
    active = refresh_hypotheses()
    if not active:
        return "No active hypotheses to verify."
    lines = ["Hypothesis verification (read-only preview):"]
    for hyp in active[:5]:
        cmd = hyp.get("verify_command", "")
        lines.append(f"- {hyp.get('title', '')} -> run: {cmd}")
    lines.append("No autonomous actions executed; verification is operator-driven.")
    return "\n".join(lines)


def compare_hypothesis_history() -> str:
    state = _load()
    history = state.get("history") or []
    if len(history) < 2:
        return "Insufficient hypothesis history for comparison."
    recent_ids = [h.get("id") for h in history[-10:] if h.get("id")]
    counts: dict[str, int] = {}
    for hid in recent_ids:
        counts[hid] = counts.get(hid, 0) + 1
    lines = ["Hypothesis recurrence (last 10 history entries):"]
    for hid, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {hid}: seen {count} times")
    return "\n".join(lines)
