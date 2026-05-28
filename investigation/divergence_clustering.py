"""Replay divergence clustering (Phase 54)."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.investigation.divergence_clustering")

CLUSTERS_PATH = DATA_DIR / "divergence_clusters.json"
CLUSTER_REPORT_DIR = PROJECT_ROOT / "reports" / "divergence_clusters"

CLUSTER_TYPES = (
    "incomplete_bar_mismatch",
    "timestamp_drift",
    "overlap_block",
    "stale_state_mismatch",
    "execution_gating_mismatch",
    "risk_mismatch",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"clusters": [], "last_run": "", "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(CLUSTERS_PATH, default=_default_state(), validator=_validate)
    if not isinstance(state.get("clusters"), list):
        state["clusters"] = []
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(CLUSTERS_PATH, state)


def _classify_line(line: str) -> str | None:
    lower = line.lower()
    if any(k in lower for k in ("incomplete", "complete=false", "incomplete_bar")):
        return "incomplete_bar_mismatch"
    if any(k in lower for k in ("timestamp", "alignment", "shifted", "index mismatch")):
        return "timestamp_drift"
    if any(k in lower for k in ("overlap", "already in position", "open position")):
        return "overlap_block"
    if any(k in lower for k in ("stale", "stale_open", "stale state")):
        return "stale_state_mismatch"
    if any(k in lower for k in ("disabled", "adapter", "gating", "blocked signal")):
        return "execution_gating_mismatch"
    if any(k in lower for k in ("risk", "exposure", "max position", "cap")):
        return "risk_mismatch"
    return None


def cluster_replay_divergences() -> dict[str, Any]:
    evidence_lines: list[str] = []
    try:
        from investigation.historical_validation import run_historical_validation_sweep

        sweep = run_historical_validation_sweep()
        evidence_lines.extend(sweep.evidence_paths[:40])
        evidence_lines.append(
            f"incomplete={sweep.incomplete_candle_usage} shifted={sweep.shifted_index_frequency} "
            f"price_mismatch={sweep.close_price_mismatches}"
        )
    except Exception as exc:
        evidence_lines.append(f"sweep unavailable: {exc}")

    try:
        from investigation.execution_investigation import show_execution_blockers

        evidence_lines.extend(show_execution_blockers().splitlines()[:30])
    except Exception:
        pass

    buckets: dict[str, list[str]] = defaultdict(list)
    for line in evidence_lines:
        kind = _classify_line(line)
        if kind:
            buckets[kind].append(line[:160])

    clusters: list[dict[str, Any]] = []
    for kind in CLUSTER_TYPES:
        samples = buckets.get(kind, [])
        if not samples:
            continue
        clusters.append(
            {
                "type": kind,
                "count": len(samples),
                "samples": samples[:8],
                "severity": "high" if len(samples) >= 5 else "medium" if len(samples) >= 2 else "low",
            }
        )
    clusters.sort(key=lambda c: c["count"], reverse=True)

    payload = {"timestamp": _now(), "clusters": clusters}
    state = _load()
    state["clusters"] = clusters
    state["last_run"] = payload["timestamp"]
    _save(state)

    try:
        CLUSTER_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = CLUSTER_REPORT_DIR / f"{ts}_clusters.json"
        path.write_text(
            __import__("json").dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Cluster report skipped: %s", exc)
    return payload


def show_divergence_clusters() -> str:
    state = _load()
    clusters = state.get("clusters") or []
    if not clusters:
        return "No divergence clusters yet. Run cluster replay divergences first."
    lines = [f"Divergence clusters ({len(clusters)}):"]
    for idx, cluster in enumerate(clusters, start=1):
        lines.append(
            f"  {idx}. {cluster['type']} count={cluster['count']} severity={cluster.get('severity', 'n/a')}"
        )
        for sample in cluster.get("samples", [])[:2]:
            lines.append(f"       - {sample[:100]}")
    return "\n".join(lines)


def explain_largest_divergence_cluster() -> str:
    state = _load()
    clusters = state.get("clusters") or []
    if not clusters:
        payload = cluster_replay_divergences()
        clusters = payload.get("clusters") or []
    if not clusters:
        return "No divergence clusters identified."
    top = clusters[0]
    lines = [
        f"Largest divergence cluster: {top['type']}",
        f"  count: {top['count']}",
        f"  severity: {top.get('severity', 'n/a')}",
        "  samples:",
    ]
    for sample in top.get("samples", [])[:5]:
        lines.append(f"    - {sample[:120]}")
    lines.append("Suggested verification:")
    if top["type"] == "overlap_block":
        lines.append("  - show stale open positions")
        lines.append("  - reconstruct execution flow")
    elif top["type"] == "execution_gating_mismatch":
        lines.append("  - inspect execution adapter")
        lines.append("  - explain top execution blocker")
    else:
        lines.append("  - run historical validation sweep")
        lines.append("  - compare replay before after")
    return "\n".join(lines)
