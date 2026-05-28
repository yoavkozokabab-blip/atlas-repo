"""Proactive operational monitoring loop (Phase 53)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.assistant.proactive_monitor")

PROACTIVE_REPORT_DIR = PROJECT_ROOT / "reports" / "proactive_monitor"
MONITOR_INTERVAL_SECONDS = 60.0

_monitor_thread: threading.Thread | None = None
_monitor_lock = threading.Lock()


def start_proactive_monitor() -> None:
    global _monitor_thread
    with _monitor_lock:
        if _monitor_thread and _monitor_thread.is_alive():
            return
        _monitor_thread = threading.Thread(
            target=_monitor_loop,
            name="jarvis-proactive-monitor",
            daemon=True,
        )
        _monitor_thread.start()


def _monitor_loop() -> None:
    while True:
        try:
            _run_checks()
        except Exception as exc:
            logger.debug("Proactive monitor cycle failed: %s", exc)
        time.sleep(MONITOR_INTERVAL_SECONDS)


def _run_checks() -> None:
    findings: list[tuple[str, str, str]] = []

    try:
        from runtime.background_tasks import get_engine

        active = get_engine().active_count()
        if active >= 3:
            findings.append(
                (
                    "Task queue backlog",
                    f"{active} background tasks active.",
                    "Run show running tasks or cancel task N.",
                )
            )
        failed = get_engine().list_failed()
        if len(failed) >= 2:
            findings.append(
                (
                    "Repeated task failures",
                    f"{len(failed)} recent failed background tasks.",
                    "Run show failed tasks and explain last result.",
                )
            )
    except Exception:
        pass

    try:
        from runtime.dashboard_health import probe_dashboard_health

        probe = probe_dashboard_health()
        status = str(probe.get("status", ""))
        if status in {"degraded", "failed"}:
            detail = str(probe.get("detail", probe.get("message", status)))
            findings.append(
                (
                    "Dashboard degraded",
                    f"Dashboard status={status}. {detail[:80]}",
                    "Run restart dashboard or show dashboard health.",
                )
            )
            from assistant.notifications import notify_dashboard_failed

            notify_dashboard_failed(f"Dashboard {status}")
    except Exception:
        pass

    try:
        from runtime.healing_engine import show_runtime_health

        health = show_runtime_health().lower()
        if "degraded" in health or "failed" in health:
            findings.append(
                (
                    "Runtime degradation",
                    health.splitlines()[0][:120],
                    "Run show healing actions or validate runtime integrity.",
                )
            )
    except Exception:
        pass

    try:
        from investigation.execution_cleanup import show_stale_open_positions

        stale = show_stale_open_positions()
        if "stale" in stale.lower() and "none" not in stale.lower():
            findings.append(
                (
                    "Stale open positions",
                    stale.splitlines()[0][:120],
                    "Run show stale open positions or propose execution cleanup patch.",
                )
            )
    except Exception:
        pass

    try:
        from investigation.execution_investigation import show_execution_blockers

        blockers = show_execution_blockers()
        lower = blockers.lower()
        if "adapter disabled" in lower or "execution disabled" in lower:
            findings.append(
                (
                    "Execution adapter disabled",
                    blockers.splitlines()[0][:120],
                    "Inspect execution adapter and enable paper adapter.",
                )
            )
        if "zero execution" in lower or "execution attempts: 0" in lower:
            findings.append(
                (
                    "Zero execution attempts",
                    "Execution attempts are still zero despite eligible signals.",
                    "Run explain top execution blocker or reconstruct execution flow.",
                )
            )
    except Exception:
        pass

    try:
        from ui.overlay_app import get_overlay_controller

        health = get_overlay_controller().health_snapshot()
        if health.get("enabled") and not health.get("qt_thread_alive"):
            findings.append(
                (
                    "Overlay failure",
                    "Overlay Qt thread is not alive.",
                    "Run recover overlay or restart overlay.",
                )
            )
    except Exception:
        pass

    if not findings:
        return

    from assistant.notifications import notify_proactive

    for title, message, action in findings[:5]:
        notify_proactive(title, message, suggested_action=action)

    try:
        PROACTIVE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = PROACTIVE_REPORT_DIR / f"{ts}_scan.json"
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "findings": [{"title": t, "message": m, "action": a} for t, m, a in findings],
        }
        path.write_text(
            __import__("json").dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Proactive report write failed: %s", exc)
