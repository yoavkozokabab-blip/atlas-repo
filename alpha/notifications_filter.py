"""Suppress noisy dev notifications in alpha mode (Phase 68)."""

from __future__ import annotations

from alpha.mode import is_alpha_mode

_DEV_KINDS = frozenset(
    {
        "investigation_completed",
        "dashboard_failed",
        "stale_positions",
        "replay_validation_passed",
        "patch_workflow_completed",
        "healing_action",
        "runtime_degraded",
    }
)


def should_suppress_notification(
    kind: str,
    *,
    title: str = "",
    message: str = "",
    severity: str = "info",
) -> bool:
    if not is_alpha_mode():
        return False
    import config

    if not getattr(config, "ALPHA_SUPPRESS_DEV_NOTIFICATIONS", True):
        return False
    kind_norm = (kind or "").lower()
    if kind_norm in _DEV_KINDS and (severity or "info").lower() != "critical":
        return True
    low = f"{title} {message}".lower()
    if any(tok in low for tok in ("trading", "backtest", "investigation", "patch workflow", "kill switch")):
        if (severity or "info").lower() != "critical":
            return True
    return False
