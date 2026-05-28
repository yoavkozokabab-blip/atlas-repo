"""Phase 37e — optional background persistence (failure-safe)."""

from __future__ import annotations

from typing import Callable

from config import ASYNC_PERSISTENCE_ENABLED
from core.logger import setup_logger

logger = setup_logger("jarvis.reliability.async_persistence")


def schedule_persistence(fn: Callable[[], None]) -> None:
    """
    Run finalize I/O on a daemon thread when enabled.
    Failures are logged only; they must not affect the command result.
    """
    if not ASYNC_PERSISTENCE_ENABLED:
        fn()
        return

    def _run() -> None:
        try:
            fn()
        except Exception as exc:
            logger.debug("Async persistence failed (non-fatal): %s", exc)

    try:
        from services.high_performance_runtime import submit_background

        submit_background(_run, workload="persistence")
    except Exception:
        _run()
