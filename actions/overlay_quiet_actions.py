"""Overlay visibility and quiet mode commands."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from ui.quiet_mode import (
    hide_overlay_window,
    is_quiet_mode,
    is_overlay_window_visible,
    quiet_mode_status_line,
    show_overlay_window,
    toggle_quiet_mode,
)


class ShowOverlayAction(BaseAction):
    intent = Intent.SHOW_OVERLAY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        show_overlay_window(reason="command_show_overlay")
        return result_success(
            Intent.SHOW_OVERLAY,
            f"Overlay shown. {quiet_mode_status_line()}",
        )


class HideOverlayAction(BaseAction):
    intent = Intent.HIDE_OVERLAY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        hide_overlay_window(reason="command_hide_overlay")
        return result_success(
            Intent.HIDE_OVERLAY,
            f"Overlay hidden. {quiet_mode_status_line()}",
        )


class ToggleQuietModeAction(BaseAction):
    intent = Intent.TOGGLE_QUIET_MODE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        enabled = toggle_quiet_mode()
        state = "enabled" if enabled else "disabled"
        return result_success(
            Intent.TOGGLE_QUIET_MODE,
            f"Quiet mode {state}. {quiet_mode_status_line()}",
            data={
                "quiet_mode": enabled,
                "overlay_visible": is_overlay_window_visible(),
            },
        )
