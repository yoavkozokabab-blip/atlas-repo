"""Periodic health watchdog and recovery coordinator for tray mode."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config import (
    PROJECT_ROOT,
    WATCHDOG_MAX_RECOVERIES_PER_HOUR,
    WATCHDOG_RECOVERY_ENABLED,
)
from core.logger import setup_logger
from services.health import HealthReport, run_jarvis_health_check
from services.runtime_monitor import get_runtime_monitor

if TYPE_CHECKING:
    from ui.tray_app import JarvisTrayApp

logger = setup_logger("jarvis.services.watchdog")

WATCHDOG_STATUS_PATH = PROJECT_ROOT / "data" / "watchdog_status.json"
WATCHDOG_INTERVAL_SECONDS = int(os.getenv("WATCHDOG_INTERVAL_SECONDS", "120"))
NOTIFY_ON_CRITICAL = os.getenv("WATCHDOG_NOTIFY_CRITICAL", "true").lower() in {
    "1",
    "true",
    "yes",
}


class WatchdogService:
    """
    Background monitor with narrow, in-process recovery for optional services.
    """

    def __init__(
        self,
        tray_app: "JarvisTrayApp",
        *,
        interval_seconds: int | None = None,
        status_path: Path | None = None,
    ) -> None:
        self._tray = tray_app
        self._interval = interval_seconds or WATCHDOG_INTERVAL_SECONDS
        self._status_path = status_path or WATCHDOG_STATUS_PATH
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_critical_notify: str | None = None
        self._recovery_times: deque[float] = deque(maxlen=max(1, WATCHDOG_MAX_RECOVERIES_PER_HOUR))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-watchdog",
            daemon=True,
        )
        self._thread.start()
        logger.info("Watchdog started (interval=%ss)", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None

    def run_once(self) -> dict[str, Any]:
        """Single health pass; persist status; notify on new critical issues."""
        report = run_jarvis_health_check(
            runtime=self._tray.runtime,
            voice_thread=self._tray._voice_thread,
            tray_running=self._tray.runtime.tray_enabled,
        )
        runtime_status = get_runtime_monitor().run_once()
        recoveries = self._recover(report, runtime_status)
        if recoveries:
            report = run_jarvis_health_check(
                runtime=self._tray.runtime,
                voice_thread=self._tray._voice_thread,
                tray_running=self._tray.runtime.tray_enabled,
            )
            runtime_status = get_runtime_monitor().run_once()
        status = self._build_status(report, runtime_status, recoveries)
        self._write_status(status)
        self._maybe_notify(report, status)
        return status

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.run_once()
            except Exception as exc:
                logger.warning("Watchdog tick failed: %s", exc)
                self._write_status(
                    {
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "overall": "critical",
                        "error": str(exc),
                        "issues": [str(exc)],
                    }
                )

    def _build_status(
        self,
        report: HealthReport,
        runtime_status: dict[str, Any] | None = None,
        recoveries: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        issues = [
            f"{c.name}: {c.message}"
            for c in report.checks
            if c.status in ("warning", "critical")
        ]
        runtime_status = runtime_status or {}
        runtime_issues = runtime_status.get("issues") or []
        for issue in runtime_issues:
            msg = issue.get("message") if isinstance(issue, dict) else str(issue)
            if msg:
                issues.append(f"runtime: {msg}")
        recoveries = recoveries or []
        return {
            "updated_at": report.checked_at or datetime.now(timezone.utc).isoformat(),
            "overall": self._overall_with_runtime(report.overall, runtime_status),
            "summary": report.summary,
            "issues": issues,
            "checks": report.to_dict()["checks"],
            "running": True,
            "interval_seconds": self._interval,
            "repairs_performed": bool(recoveries),
            "recoveries": recoveries,
            "recovery_enabled": WATCHDOG_RECOVERY_ENABLED,
            "runtime_monitor": runtime_status,
        }

    def _overall_with_runtime(self, health_overall: str, runtime_status: dict[str, Any]) -> str:
        runtime_overall = runtime_status.get("overall", "ok")
        if "critical" in {health_overall, runtime_overall}:
            return "critical"
        if "warning" in {health_overall, runtime_overall}:
            return "warning"
        return health_overall

    def _can_recover(self) -> bool:
        if not WATCHDOG_RECOVERY_ENABLED:
            return False
        now = time.monotonic()
        while self._recovery_times and now - self._recovery_times[0] > 3600:
            self._recovery_times.popleft()
        return len(self._recovery_times) < max(1, WATCHDOG_MAX_RECOVERIES_PER_HOUR)

    def _recover(
        self,
        report: HealthReport,
        runtime_status: dict[str, Any],
    ) -> list[dict[str, Any]]:
        del report
        if not self._can_recover():
            return []

        restart = getattr(self._tray, "restart_background_services", None)
        raw_actions = restart(reason="watchdog") if callable(restart) else []
        actions = list(raw_actions) if isinstance(raw_actions, (list, tuple)) else []
        runtime_issues = runtime_status.get("issues") or []
        if runtime_issues:
            try:
                from ui.overlay_app import get_overlay_controller

                if self._tray.runtime.overlay_enabled:
                    recovered = get_overlay_controller().recover_if_crashed(
                        reason="watchdog_runtime_issue"
                    )
                    if recovered:
                        actions.append(
                            {
                                "component": "overlay",
                                "action": "restart_qt_thread",
                                "ok": True,
                                "reason": "watchdog_runtime_issue",
                            }
                        )
            except Exception as exc:
                actions.append(
                    {
                        "component": "overlay",
                        "action": "restart_qt_thread",
                        "ok": False,
                        "reason": "watchdog_runtime_issue",
                        "detail": str(exc),
                    }
                )

        if not actions:
            return []

        monitor = get_runtime_monitor()
        for action in actions:
            self._recovery_times.append(time.monotonic())
            monitor.record_recovery(
                str(action.get("component", "runtime")),
                str(action.get("action", "recover")),
                reason=str(action.get("reason", "watchdog")),
                ok=bool(action.get("ok", False)),
                detail=str(action.get("detail", "")),
            )
        return actions

    def _write_status(self, payload: dict[str, Any]) -> None:
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        self._status_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _maybe_notify(self, report: HealthReport, status: dict[str, Any]) -> None:
        del report
        if status.get("overall") != "critical" or not NOTIFY_ON_CRITICAL:
            return
        fingerprint = "|".join(status.get("issues", []))[:200]
        if fingerprint == self._last_critical_notify:
            return
        self._last_critical_notify = fingerprint
        try:
            from ui.notifications import notify

            msg = status.get("issues", ["Critical health issue"])[0]
            notify("JARVIS Watchdog", msg[:240], icon=self._tray._icon)
        except Exception as exc:
            logger.debug("Watchdog notify failed: %s", exc)

    @staticmethod
    def load_status(path: Path | None = None) -> dict[str, Any]:
        p = path or WATCHDOG_STATUS_PATH
        if not p.is_file():
            return {
                "overall": "unknown",
                "summary": "Watchdog has not written status yet.",
                "issues": [],
            }
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "overall": "warning",
                "summary": f"Could not read watchdog status: {exc}",
                "issues": [],
            }
