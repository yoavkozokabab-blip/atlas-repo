"""Continuous autonomous monitoring loop (Phase 54)."""

from __future__ import annotations

import time

from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.continuous_monitor")

_last_tick = 0.0
_TICK_SECONDS = 15 * 60


def run_continuous_monitor_tick() -> list[str]:
    """Read-only monitoring tick with proactive alerts."""
    global _last_tick
    now = time.monotonic()
    if now - _last_tick < _TICK_SECONDS:
        return []
    _last_tick = now

    alerts: list[str] = []
    try:
        from investigation.blocker_trends import detect_trend_anomalies, record_blocker_snapshot

        record_blocker_snapshot(source="continuous_monitor")
        alerts.extend(detect_trend_anomalies())
    except Exception as exc:
        logger.debug("Blocker monitor tick: %s", exc)

    try:
        from investigation.execution_cleanup import show_stale_open_positions

        stale = show_stale_open_positions()
        if "stale" in stale.lower() and "none" not in stale.lower():
            alerts.append("Stale open positions remain elevated")
    except Exception:
        pass

    try:
        from investigation.execution_investigation import show_execution_blockers

        blockers = show_execution_blockers().lower()
        if "disabled" in blockers:
            alerts.append("Execution disabled for extended period despite eligible signals")
    except Exception:
        pass

    try:
        from investigation.divergence_clustering import _load as load_clusters

        clusters = load_clusters().get("clusters") or []
        if clusters and clusters[0].get("type") == "stale_state_mismatch":
            alerts.append("Replay mismatches cluster around stale state transitions")
    except Exception:
        pass

    if not alerts:
        return []

    from assistant.intelligence_timeline import append_timeline_entry
    from assistant.notifications import notify_proactive

    emitted: list[str] = []
    for alert in alerts[:5]:
        append_timeline_entry(
            "continuous_monitor",
            alert,
            severity="warning",
            source="continuous_monitor",
            metadata={"suggested_action": "run investigation cycle"},
        )
        notify_proactive(
            "Continuous monitor alert",
            alert,
            suggested_action="run investigation cycle",
        )
        emitted.append(alert)
    return emitted
