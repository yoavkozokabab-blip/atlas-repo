"""Process-wide watchdog launcher (Sprint 3.2 / B02)."""

from __future__ import annotations

import threading
from typing import Any

from core.logger import setup_logger
from core.runtime_state import RuntimeState, get_runtime_state
from services.watchdog_context import WatchdogContext

logger = setup_logger("jarvis.services.watchdog_runtime")

_lock = threading.Lock()
_watchdog: Any | None = None
_context: WatchdogContext | None = None


def is_watchdog_running() -> bool:
    wd = _watchdog
    thread = getattr(wd, "_thread", None) if wd is not None else None
    return thread is not None and thread.is_alive()


def get_process_watchdog() -> Any | None:
    return _watchdog


def attach_tray_to_watchdog(tray_app: Any) -> None:
    """Bind tray app for recovery actions on an already-running watchdog."""
    global _context
    if _context is None:
        _context = WatchdogContext(get_runtime_state(), tray_app=tray_app)
    else:
        _context.tray_app = tray_app
        _context.runtime.tray_enabled = True


def ensure_process_watchdog(
    *,
    runtime: RuntimeState | None = None,
    tray_app: Any | None = None,
) -> Any | None:
    """
    Start the periodic watchdog once per process (CLI, voice, tray).

    Idempotent — safe to call from main() and tray startup.
    """
    global _watchdog, _context
    runtime = runtime or get_runtime_state()
    with _lock:
        if is_watchdog_running():
            if tray_app is not None:
                attach_tray_to_watchdog(tray_app)
            return _watchdog

        from services.watchdog import WatchdogService

        _context = WatchdogContext(runtime, tray_app=tray_app)
        _watchdog = WatchdogService(_context)
        _watchdog.start()
        logger.info("Process watchdog started (tray=%s)", tray_app is not None)
        try:
            _watchdog.run_once()
        except Exception as exc:
            logger.debug("Initial watchdog tick: %s", exc)
        return _watchdog


def stop_process_watchdog() -> None:
    global _watchdog, _context
    with _lock:
        if _watchdog is not None:
            try:
                _watchdog.stop()
            except Exception as exc:
                logger.debug("Watchdog stop: %s", exc)
        _watchdog = None
        _context = None
