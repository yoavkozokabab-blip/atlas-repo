"""Blocker trend tracking over time (Phase 54)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.investigation.blocker_trends")

TRENDS_PATH = DATA_DIR / "blocker_trends.json"
TREND_REPORT_DIR = PROJECT_ROOT / "reports" / "blocker_trends"
MAX_SNAPSHOTS = 200

KNOWN_BLOCKER_KEYS = (
    "overlap",
    "stale",
    "execution disabled",
    "adapter",
    "risk cap",
    "max position",
    "market closed",
    "kill switch",
    "last bar",
    "duplicate",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {"snapshots": [], "updated_at": ""}


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(TRENDS_PATH, default=_default_state(), validator=_validate)
    if "snapshots" not in state or not isinstance(state["snapshots"], list):
        state["snapshots"] = []
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    atomic_write_json(TRENDS_PATH, state)
    try:
        TREND_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = TREND_REPORT_DIR / f"{ts}_blocker_trends.json"
        path.write_text(
            __import__("json").dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Blocker trend report skipped: %s", exc)


def _extract_blocker_counts() -> dict[str, int]:
    counts: Counter[str] = Counter()
    try:
        from investigation.execution_investigation import rank_execution_block_reasons

        body = rank_execution_block_reasons()
        for line in body.splitlines():
            lower = line.lower()
            for key in KNOWN_BLOCKER_KEYS:
                if key in lower:
                    counts[key] += 1
            if "count=" in lower:
                counts[line.split(":")[0].strip().lower()[:80]] += 1
    except Exception as exc:
        logger.debug("Blocker rank unavailable: %s", exc)
        counts["unknown"] += 1
    try:
        from investigation.execution_flow import run_execution_flow_reconstruction

        audit = run_execution_flow_reconstruction()
        top = (audit.top_blocker or "none").lower()
        for key in KNOWN_BLOCKER_KEYS:
            if key in top:
                counts[key] += 2
        counts[top[:80] or "none"] += 3
    except Exception:
        pass
    return dict(counts)


def record_blocker_snapshot(*, source: str = "cycle") -> dict[str, Any]:
    counts = _extract_blocker_counts()
    snapshot = {"timestamp": _now(), "source": source, "counts": counts}
    state = _load()
    snapshots: list[dict[str, Any]] = state["snapshots"]
    snapshots.append(snapshot)
    state["snapshots"] = snapshots[-MAX_SNAPSHOTS:]
    _save(state)
    return snapshot


def show_blocker_trends(*, limit: int = 8) -> str:
    state = _load()
    snapshots = state["snapshots"][-limit:]
    if not snapshots:
        return "No blocker trend snapshots yet. Run an investigation cycle first."
    lines = [f"Blocker trends ({len(snapshots)} recent snapshots):"]
    for snap in snapshots:
        ts = snap.get("timestamp", "")[:19]
        top = sorted((snap.get("counts") or {}).items(), key=lambda x: x[1], reverse=True)[:3]
        summary = ", ".join(f"{k}={v}" for k, v in top) or "none"
        lines.append(f"  {ts} [{snap.get('source', '?')}]: {summary}")
    return "\n".join(lines)


def compare_blocker_trends() -> str:
    state = _load()
    snapshots = state["snapshots"]
    if len(snapshots) < 2:
        return "Need at least two snapshots to compare blocker trends."
    prev = snapshots[-2].get("counts") or {}
    curr = snapshots[-1].get("counts") or {}
    keys = set(prev) | set(curr)
    lines = ["Blocker trend comparison (previous vs latest):"]
    for key in sorted(keys):
        before = int(prev.get(key, 0))
        after = int(curr.get(key, 0))
        delta = after - before
        if delta == 0 and before == 0:
            continue
        direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
        lines.append(f"  {key}: {before} -> {after} ({direction})")
    if len(lines) == 1:
        lines.append("  - no significant deltas")
    return "\n".join(lines)


def explain_dominant_blocker() -> str:
    state = _load()
    if not state["snapshots"]:
        record_blocker_snapshot(source="on_demand")
        state = _load()
    totals: Counter[str] = Counter()
    for snap in state["snapshots"][-20:]:
        for key, count in (snap.get("counts") or {}).items():
            totals[key] += int(count)
    if not totals:
        return "No dominant blocker identified yet."
    dominant, score = totals.most_common(1)[0]
    lines = [
        f"Dominant blocker trend: {dominant} (score={score})",
        "Interpretation:",
    ]
    if "overlap" in dominant or "stale" in dominant:
        lines.append("  - likely stale open_positions / overlap policy suppressing entries")
        lines.append("  - verify: show stale open positions")
    elif "disabled" in dominant or "adapter" in dominant:
        lines.append("  - execution adapter may be disabled")
        lines.append("  - verify: inspect execution adapter")
    elif "risk" in dominant or "max position" in dominant:
        lines.append("  - risk cap or max positions may be binding")
        lines.append("  - verify: show current execution risk")
    else:
        lines.append("  - verify: explain top execution blocker")
    return "\n".join(lines)


def show_blocker_history(*, limit: int = 15) -> str:
    state = _load()
    snapshots = state["snapshots"][-limit:]
    if not snapshots:
        return "Blocker history empty."
    lines = [f"Blocker history ({len(snapshots)} entries):"]
    for snap in snapshots:
        ts = snap.get("timestamp", "")[:19]
        counts = snap.get("counts") or {}
        dominant = max(counts.items(), key=lambda x: x[1])[0] if counts else "none"
        lines.append(f"  {ts} dominant={dominant} source={snap.get('source', '?')}")
    return "\n".join(lines)


def detect_trend_anomalies() -> list[str]:
    """Return human-readable anomaly strings for monitors."""
    state = _load()
    snapshots = state["snapshots"]
    if len(snapshots) < 2:
        return []
    prev = snapshots[-2].get("counts") or {}
    curr = snapshots[-1].get("counts") or {}
    anomalies: list[str] = []
    for key in set(prev) | set(curr):
        before = int(prev.get(key, 0))
        after = int(curr.get(key, 0))
        if before <= 0 and after > 0:
            anomalies.append(f"New blocker appeared: {key}")
        elif before > 0 and after >= before * 2:
            pct = int(((after - before) / max(before, 1)) * 100)
            anomalies.append(f"{key} frequency increased {pct}%")
    return anomalies
