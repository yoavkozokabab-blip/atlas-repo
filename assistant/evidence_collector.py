"""Autonomous evidence collection for root-cause verification (Phase 55)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.evidence_collector")

EVIDENCE_PATH = DATA_DIR / "root_cause_evidence.json"
EVIDENCE_REPORT_DIR = PROJECT_ROOT / "reports" / "root_cause_engine"
MAX_SNAPSHOTS = 150


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"snapshots": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(EVIDENCE_PATH, default=_default_state(), validator=_validate)
    if not isinstance(state.get("snapshots"), list):
        state["snapshots"] = []
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(EVIDENCE_PATH, state)
    try:
        EVIDENCE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = EVIDENCE_REPORT_DIR / f"{ts}_evidence.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Evidence report skipped: %s", exc)


def _safe(label: str, fn) -> str:
    try:
        body = fn()
        return str(body or "")[:1200]
    except Exception as exc:
        return f"{label} unavailable: {exc}"


def collect_evidence_snapshot(*, source: str = "manual") -> dict[str, Any]:
    """Collect read-only operational evidence snapshot."""
    snapshot = {
        "timestamp": _now(),
        "source": source,
        "runtime_health": _safe("runtime", lambda: __import__("runtime.healing_engine", fromlist=["show_runtime_health"]).show_runtime_health()),
        "execution_blockers": _safe(
            "blockers",
            lambda: __import__("investigation.execution_investigation", fromlist=["show_execution_blockers"]).show_execution_blockers(),
        ),
        "stale_positions": _safe(
            "stale",
            lambda: __import__("investigation.execution_cleanup", fromlist=["show_stale_open_positions"]).show_stale_open_positions(),
        ),
        "execution_risk": _safe(
            "risk",
            lambda: __import__("operational.trading_operations", fromlist=["show_current_execution_risk"]).show_current_execution_risk(),
        ),
        "adapter_state": _safe(
            "adapter",
            lambda: __import__("investigation.execution_investigation", fromlist=["inspect_execution_adapter"]).inspect_execution_adapter(),
        ),
        "dashboard_health": _safe(
            "dashboard",
            lambda: str(__import__("runtime.dashboard_health", fromlist=["probe_dashboard_health"]).probe_dashboard_health()),
        ),
        "divergence_clusters": _safe(
            "divergence",
            lambda: __import__("investigation.divergence_clustering", fromlist=["show_divergence_clusters"]).show_divergence_clusters(),
        ),
        "healing_events": _safe(
            "healing",
            lambda: __import__("runtime.healing_engine", fromlist=["show_healing_actions"]).show_healing_actions(),
        ),
        "execution_flow": _safe(
            "flow",
            lambda: __import__("investigation.execution_flow", fromlist=["reconstruct_execution_flow"]).reconstruct_execution_flow()[:800],
        ),
    }
    state = _load()
    snapshots: list[dict[str, Any]] = state["snapshots"]
    snapshots.append(snapshot)
    state["snapshots"] = snapshots[-MAX_SNAPSHOTS:]
    _save(state)
    return snapshot


def get_latest_evidence() -> dict[str, Any] | None:
    snapshots = _load().get("snapshots") or []
    return snapshots[-1] if snapshots else None


def get_evidence_for_hypothesis(hypothesis_id: str) -> list[str]:
    """Return evidence strings relevant to a hypothesis id."""
    latest = get_latest_evidence()
    if not latest:
        latest = collect_evidence_snapshot(source="on_demand")
    items: list[str] = []
    mapping = {
        "overlap_stale_positions": ("stale_positions", "execution_blockers"),
        "adapter_disabled": ("adapter_state", "execution_blockers"),
        "last_bar_filter": ("execution_blockers", "execution_flow"),
        "stale_telemetry_risk": ("execution_risk", "stale_positions"),
        "cluster_divergence": ("divergence_clusters",),
    }
    keys = mapping.get(hypothesis_id, tuple(latest.keys()))
    for key in keys:
        value = latest.get(key, "")
        if value and "unavailable" not in value.lower():
            items.append(f"{key}: {str(value).splitlines()[0][:160]}")
    return items[:8]
