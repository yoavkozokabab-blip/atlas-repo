"""Autonomous investigation scheduler (Phase 54)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from config import DATA_DIR, PROJECT_ROOT
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.investigation_scheduler")

SCHEDULER_PATH = DATA_DIR / "investigation_scheduler.json"
SCHEDULER_REPORT_DIR = PROJECT_ROOT / "reports" / "autonomous_investigations"

DEFAULT_JOBS: dict[str, dict[str, Any]] = {
    "health_15m": {
        "label": "Runtime/trading health",
        "interval_seconds": 15 * 60,
        "runner": "health_scan",
    },
    "blockers_1h": {
        "label": "Execution blocker analysis",
        "interval_seconds": 60 * 60,
        "runner": "blocker_scan",
    },
    "verification_2h": {
        "label": "Root cause verification",
        "interval_seconds": 2 * 60 * 60,
        "runner": "verification_scan",
    },
    "nightly_validation": {
        "label": "Historical validation sweep",
        "interval_seconds": 24 * 60 * 60,
        "runner": "nightly_validation",
        "night_only": True,
    },
    "nightly_divergence": {
        "label": "Replay divergence clustering",
        "interval_seconds": 24 * 60 * 60,
        "runner": "nightly_divergence",
        "night_only": True,
    },
    "startup_integrity": {
        "label": "Operational integrity scan",
        "interval_seconds": 0,
        "runner": "startup_integrity",
        "run_once": True,
    },
}

_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "paused": False,
        "last_runs": {},
        "startup_integrity_done": False,
        "updated_at": "",
    }


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(SCHEDULER_PATH, default=_default_state(), validator=_validate)
    state.setdefault("last_runs", {})
    return state


def _save(state: dict[str, Any]) -> None:
    state["updated_at"] = _now_iso()
    atomic_write_json(SCHEDULER_PATH, state)


def _run_health_scan() -> None:
    from assistant.investigation_cycles import run_investigation_cycle

    run_investigation_cycle(kind="scheduled_health")


def _run_blocker_scan() -> None:
    from investigation.blocker_trends import record_blocker_snapshot
    from assistant.hypothesis_engine import refresh_hypotheses
    from assistant.root_cause_engine import sync_root_causes

    record_blocker_snapshot(source="scheduled_blockers")
    refresh_hypotheses()
    sync_root_causes()


def _run_verification_scan() -> None:
    from assistant.root_cause_engine import verify_root_causes

    verify_root_causes()


def _run_nightly_validation() -> None:
    from assistant.investigation_cycles import run_nightly_investigation

    run_nightly_investigation()


def _run_nightly_divergence() -> None:
    from investigation.divergence_clustering import cluster_replay_divergences

    cluster_replay_divergences()


def _run_startup_integrity() -> None:
    from assistant.investigation_cycles import run_investigation_cycle

    run_investigation_cycle(kind="startup_integrity")


_RUNNERS: dict[str, Callable[[], None]] = {
    "health_scan": _run_health_scan,
    "blocker_scan": _run_blocker_scan,
    "verification_scan": _run_verification_scan,
    "nightly_validation": _run_nightly_validation,
    "nightly_divergence": _run_nightly_divergence,
    "startup_integrity": _run_startup_integrity,
}


def _is_night_window() -> bool:
    hour = datetime.now(timezone.utc).hour
    return hour >= 1 and hour <= 5


def _due(job_id: str, job: dict[str, Any], state: dict[str, Any]) -> bool:
    if job.get("run_once"):
        if job_id == "startup_integrity" and state.get("startup_integrity_done"):
            return False
        return True
    interval = int(job.get("interval_seconds") or 0)
    if interval <= 0:
        return False
    if job.get("night_only") and not _is_night_window():
        return False
    last = state.get("last_runs", {}).get(job_id)
    if not last:
        return True
    try:
        last_ts = datetime.fromisoformat(str(last).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return True
    return (time.time() - last_ts) >= interval


def scheduler_tick(*, force: bool = False) -> list[str]:
    state = _load()
    if state.get("paused") and not force:
        return []
    ran: list[str] = []
    for job_id, job in DEFAULT_JOBS.items():
        if not force and not _due(job_id, job, state):
            continue
        runner_name = str(job.get("runner", ""))
        runner = _RUNNERS.get(runner_name)
        if runner is None:
            continue
        try:
            logger.info("Running scheduled investigation job: %s", job_id)
            runner()
            state.setdefault("last_runs", {})[job_id] = _now_iso()
            if job.get("run_once"):
                state["startup_integrity_done"] = True
            ran.append(job_id)
        except Exception as exc:
            logger.exception("Scheduled job %s failed: %s", job_id, exc)
    _save(state)
    return ran


def _scheduler_loop() -> None:
    while True:
        try:
            scheduler_tick()
            from assistant.continuous_monitor import run_continuous_monitor_tick

            run_continuous_monitor_tick()
        except Exception as exc:
            logger.debug("Scheduler loop error: %s", exc)
        time.sleep(60.0)


def start_investigation_scheduler() -> None:
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="jarvis-investigation-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()


def show_investigation_schedule() -> str:
    state = _load()
    lines = [
        "Investigation schedule:",
        f"  loop: {'PAUSED' if state.get('paused') else 'ACTIVE'}",
    ]
    for job_id, job in DEFAULT_JOBS.items():
        interval = int(job.get("interval_seconds") or 0)
        every = f"{interval // 60}m" if interval and interval < 3600 else (
            f"{interval // 3600}h" if interval else "startup/on-demand"
        )
        last = state.get("last_runs", {}).get(job_id, "never")
        lines.append(f"  - {job_id}: {job.get('label')} every {every} last={str(last)[:19]}")
    return "\n".join(lines)


def pause_investigation_loop() -> str:
    state = _load()
    state["paused"] = True
    _save(state)
    return "Investigation loop paused."


def resume_investigation_loop() -> str:
    state = _load()
    state["paused"] = False
    _save(state)
    return "Investigation loop resumed."


def run_investigation_cycle_now() -> str:
    from assistant.investigation_cycles import run_investigation_cycle

    payload = run_investigation_cycle(kind="manual")
    return (
        f"Investigation cycle complete ({payload.get('elapsed_seconds', 0)}s). "
        f"Anomalies: {len(payload.get('anomalies') or [])}. "
        f"Report: {payload.get('report_markdown', 'n/a')}"
    )


def run_nightly_investigation_now() -> str:
    from assistant.investigation_cycles import run_nightly_investigation

    payload = run_nightly_investigation()
    return (
        f"Nightly investigation complete ({payload.get('elapsed_seconds', 0)}s). "
        f"Report: {payload.get('report_markdown', 'n/a')}"
    )


def get_overlay_snapshot() -> dict[str, Any]:
    """Phase 54 overlay snapshot for autonomous investigation state (read-only, cached)."""
    state = _load()
    snap: dict[str, Any] = {
        "loop": "paused" if state.get("paused") else "active",
        "dominant_blocker": "",
        "top_hypothesis": "",
        "runtime_severity": "unknown",
        "unresolved_anomalies": 0,
        "latest_finding": "",
    }
    try:
        from investigation.blocker_trends import _load as load_blocker_trends

        snapshots = load_blocker_trends().get("snapshots") or []
        if snapshots:
            latest = snapshots[-1]
            counts = latest.get("counts") or {}
            if counts:
                top = max(counts.items(), key=lambda item: item[1])
                snap["dominant_blocker"] = f"{top[0]} ({top[1]})"[:100]
    except Exception:
        pass
    try:
        from assistant.hypothesis_engine import _load as load_hypotheses

        active = load_hypotheses().get("active") or []
        if active:
            snap["top_hypothesis"] = str(active[0].get("title", ""))[:100]
    except Exception:
        pass
    try:
        from assistant.intelligence_timeline import _load as load_timeline

        entries = load_timeline().get("entries") or []
        unresolved = [
            e
            for e in entries
            if isinstance(e, dict) and e.get("severity") in {"warning", "critical"} and not e.get("resolved")
        ]
        snap["unresolved_anomalies"] = len(unresolved[-10:])
        if unresolved:
            snap["runtime_severity"] = str(unresolved[-1].get("severity", "warning"))
        elif entries:
            snap["runtime_severity"] = "ok"
    except Exception:
        pass
    try:
        reports_dir = SCHEDULER_REPORT_DIR
        if reports_dir.is_dir():
            reports = sorted(reports_dir.glob("*_cycle.json"), reverse=True)
            if reports:
                payload = __import__("json").loads(reports[0].read_text(encoding="utf-8"))
                anomalies = payload.get("anomalies") or []
                if anomalies:
                    snap["latest_finding"] = str(anomalies[0])[:100]
                    if snap["runtime_severity"] == "unknown":
                        snap["runtime_severity"] = "warning"
    except Exception:
        pass
    return snap


def reset_scheduler_for_tests() -> None:
    global _scheduler_thread
    with _scheduler_lock:
        _scheduler_thread = None
