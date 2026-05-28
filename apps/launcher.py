"""Launch approved apps via os.startfile (no shell)."""

from __future__ import annotations

import os
from pathlib import Path

from apps.app_registry import ApprovedApp
from apps.discovery import DiscoveredApp
from apps.safety import SafetyError, validate_launch_path
from core.logger import setup_logger

logger = setup_logger("jarvis.apps.launcher")


def launch_app(
    *,
    shortcut_path: Path | str,
    display_name: str = "application",
) -> str:
    """
    Open app using shortcut path only (preferred).
    Uses os.startfile — never shell=True.
    """
    path = validate_launch_path(shortcut_path)
    if path.suffix.lower() != ".lnk":
        raise SafetyError("Only .lnk shortcuts are approved for launch.")

    os.startfile(str(path))  # noqa: S606 — controlled allowlisted shortcut only
    logger.info("Launched %s via %s", display_name, path)
    return f"Opened {display_name}."


def launch_discovered(app: DiscoveredApp) -> str:
    return launch_app(
        shortcut_path=app.shortcut_path,
        display_name=app.display_name,
    )


def launch_approved(app: ApprovedApp) -> str:
    return launch_app(
        shortcut_path=app.shortcut_path,
        display_name=app.display_name,
    )
