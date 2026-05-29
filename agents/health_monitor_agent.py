"""Health Monitor Agent — system health, storage checks, dependency validation (Sprint 3 / S3.5).

Wraps services/health.py and adds the storage checks identified in the audit
(VF-1: backup growth, VF-2: JSONL rotation, VF-3: memory vacuum).

A 30-second heartbeat daemon thread is registered with ThreadRegistry so the
watchdog can detect if the health monitor itself dies.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.base import AgentCapability, AgentId
from core.logger import setup_logger

logger = setup_logger("jarvis.agents.health_monitor")

_AGENT_ID = AgentId.HEALTH_MONITOR

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Health Monitor Agent",
    owns=(
        "system health checks (disk, Tesseract, Ollama, voice thread)",
        "storage growth monitoring (backups, JSONL logs, screenshots)",
        "memory vacuum scheduling",
        "dependency availability reporting (win32gui, Tesseract, Playwright)",
        "thread registry heartbeat",
    ),
    runtime_modules=(
        "services/health.py",
        "core/startup_validation.py",
        "core/thread_registry.py",
        "core/persistent_json.py",
    ),
)

# -----------------------------------------------------------------------
# Storage health thresholds (aligned with audit findings VF-1 / VF-2)
# -----------------------------------------------------------------------
_BACKUP_WARNING_COUNT = 500
_BACKUP_CRITICAL_COUNT = 2_000
_JSONL_WARNING_BYTES = 5_000_000   # 5 MB
_JSONL_CRITICAL_BYTES = 20_000_000  # 20 MB


@dataclass
class StorageHealthItem:
    name: str
    status: str          # "ok" | "warning" | "critical"
    message: str
    value: Any = None


def run_storage_health_checks() -> list[StorageHealthItem]:
    """
    Check backup count and JSONL sizes against audit thresholds.
    Returns a list of StorageHealthItem, one per checked resource.
    """
    from config import DATA_DIR

    items: list[StorageHealthItem] = []

    # VF-1: backup directory file count
    backup_dir = Path(DATA_DIR) / "backups"
    try:
        count = sum(1 for _ in backup_dir.glob("*.json")) if backup_dir.is_dir() else 0
        if count >= _BACKUP_CRITICAL_COUNT:
            items.append(StorageHealthItem(
                "backups_count", "critical",
                f"data/backups/ has {count} files (limit={_BACKUP_CRITICAL_COUNT}); "
                "startup cleanup may not have run yet.",
                value=count,
            ))
        elif count >= _BACKUP_WARNING_COUNT:
            items.append(StorageHealthItem(
                "backups_count", "warning",
                f"data/backups/ has {count} files (warning={_BACKUP_WARNING_COUNT}).",
                value=count,
            ))
        else:
            items.append(StorageHealthItem(
                "backups_count", "ok",
                f"data/backups/ has {count} files.",
                value=count,
            ))
    except OSError as exc:
        items.append(StorageHealthItem("backups_count", "warning", f"Cannot check backups: {exc}"))

    # VF-2: JSONL file sizes
    jsonl_files = {
        "observability_events.jsonl": Path(DATA_DIR) / "observability_events.jsonl",
        "command_history.jsonl":       Path(DATA_DIR) / "command_history.jsonl",
        "command_audit.jsonl":         Path(DATA_DIR) / "command_audit.jsonl",
        "runtime_traces.jsonl":        Path(DATA_DIR) / "runtime_traces.jsonl",
    }
    for label, path in jsonl_files.items():
        try:
            size = path.stat().st_size if path.is_file() else 0
            if size >= _JSONL_CRITICAL_BYTES:
                items.append(StorageHealthItem(
                    f"jsonl_{label}", "critical",
                    f"{label}: {size // 1_000_000} MB (>{_JSONL_CRITICAL_BYTES // 1_000_000} MB critical)",
                    value=size,
                ))
            elif size >= _JSONL_WARNING_BYTES:
                items.append(StorageHealthItem(
                    f"jsonl_{label}", "warning",
                    f"{label}: {size // 1_000_000} MB (>{_JSONL_WARNING_BYTES // 1_000_000} MB warning)",
                    value=size,
                ))
            else:
                items.append(StorageHealthItem(
                    f"jsonl_{label}", "ok",
                    f"{label}: {size // 1_024} KB",
                    value=size,
                ))
        except OSError as exc:
            items.append(StorageHealthItem(f"jsonl_{label}", "warning", f"Cannot stat {label}: {exc}"))

    return items


def format_storage_health_report() -> str:
    items = run_storage_health_checks()
    lines = ["Storage health:"]
    for item in items:
        lines.append(f"  [{item.status}] {item.name}: {item.message}")
    return "\n".join(lines)


# -----------------------------------------------------------------------
# Health Monitor Agent class
# -----------------------------------------------------------------------

class HealthMonitorAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def __init__(self) -> None:
        self._heartbeat_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_storage_items: list[StorageHealthItem] = []
        self._last_check_ts: float = 0.0

    def start(self) -> None:
        """Start the 30-second heartbeat daemon thread and register it."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="jarvis-health-monitor",
            daemon=True,
        )
        self._heartbeat_thread.start()
        # S3.5: register with ThreadRegistry so the watchdog detects unexpected death.
        try:
            from core.thread_registry import get_thread_registry
            get_thread_registry().register("jarvis-health-monitor", self._heartbeat_thread)
        except Exception:
            pass
        logger.info("HealthMonitorAgent started (30s heartbeat)")

    def stop(self) -> None:
        self._stop.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)
        self._heartbeat_thread = None
        try:
            from core.thread_registry import get_thread_registry
            get_thread_registry().deregister("jarvis-health-monitor")
        except Exception:
            pass

    def _heartbeat_loop(self) -> None:
        """Run storage health checks every 30 seconds; surface critical issues."""
        while not self._stop.wait(30.0):
            try:
                self._last_storage_items = run_storage_health_checks()
                self._last_check_ts = time.monotonic()
                critical = [i for i in self._last_storage_items if i.status == "critical"]
                if critical:
                    for item in critical:
                        logger.critical("Storage health CRITICAL: %s", item.message)
                    try:
                        from ui.overlay_app import notify_overlay_error
                        msg = critical[0].message[:200]
                        notify_overlay_error(f"Storage: {msg}")
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning("HealthMonitorAgent heartbeat error: %s", exc)

    def health_check(self) -> bool:
        """Returns True when the health module is importable and storage is not critical."""
        try:
            from services.health import run_jarvis_health_check  # noqa: F401
            items = run_storage_health_checks()
            return not any(i.status == "critical" for i in items)
        except Exception:
            return False

    def get_storage_status(self) -> list[StorageHealthItem]:
        """Return the most recent storage check results (updated by heartbeat)."""
        if not self._last_storage_items:
            self._last_storage_items = run_storage_health_checks()
        return self._last_storage_items

    def run_full_health_check(self, *, runtime: Any = None) -> Any:
        """Delegate to services/health.py for a full system health pass."""
        from services.health import run_jarvis_health_check
        return run_jarvis_health_check(runtime=runtime)


_health_monitor_agent: HealthMonitorAgent | None = None


def get_health_monitor_agent() -> HealthMonitorAgent:
    global _health_monitor_agent
    if _health_monitor_agent is None:
        _health_monitor_agent = HealthMonitorAgent()
    return _health_monitor_agent
