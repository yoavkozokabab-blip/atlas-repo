"""Alpha mode configuration and safe defaults (Phase 68)."""

from __future__ import annotations

import config
from core.logger import setup_logger

logger = setup_logger("jarvis.alpha.mode")


def is_alpha_mode() -> bool:
    return bool(getattr(config, "ALPHA_MODE", False))


def is_developer_mode() -> bool:
    return bool(getattr(config, "DEVELOPER_MODE", False))


def apply_alpha_runtime_defaults() -> None:
    """Apply safer defaults when ALPHA_MODE is enabled."""
    if not is_alpha_mode():
        return
    config.COMPUTER_CONTROL_ENABLED = False
    config.DESKTOP_OPERATOR_SAFE_MODE = True
    config.PATCH_APPLY_ENABLED = False
    config.ALPHA_SUPPRESS_DEV_NOTIFICATIONS = True
    config.ALPHA_FORCE_APPROVAL_GATES = True
    if not hasattr(config, "_ALPHA_DEFAULTS_APPLIED"):
        config._ALPHA_DEFAULTS_APPLIED = True  # type: ignore[attr-defined]
        logger.info("Alpha mode: applied safe runtime defaults")
