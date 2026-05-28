"""Background quiet mode — overlay hidden until wake or explicit command."""

from __future__ import annotations

from config import (
    BACKGROUND_MODE,
    OVERLAY_SHOW_ON_WAKE,
    OVERLAY_START_HIDDEN,
)

_HIDDEN_COMMANDS = frozenset(
    {
        "hide overlay",
        "toggle quiet mode",
    }
)

_quiet_enabled: bool = BACKGROUND_MODE
_overlay_window_visible: bool = not (BACKGROUND_MODE and OVERLAY_START_HIDDEN)


def reset_quiet_mode_state() -> None:
    """Test helper — restore defaults from config."""
    global _quiet_enabled, _overlay_window_visible
    _quiet_enabled = BACKGROUND_MODE
    _overlay_window_visible = not (BACKGROUND_MODE and OVERLAY_START_HIDDEN)


def init_quiet_mode_from_config() -> None:
    reset_quiet_mode_state()


def is_quiet_mode() -> bool:
    return _quiet_enabled


def set_quiet_mode(enabled: bool) -> None:
    global _quiet_enabled, _overlay_window_visible
    _quiet_enabled = enabled
    if not enabled:
        _overlay_window_visible = True


def is_overlay_window_visible() -> bool:
    if not _quiet_enabled:
        return True
    return _overlay_window_visible


def show_overlay_window(*, reason: str = "") -> None:
    """Reveal HUD window (subsystem may already be running)."""
    global _overlay_window_visible
    del reason
    _overlay_window_visible = True
    try:
        from core.runtime_state import get_runtime_state

        rt = get_runtime_state()
        rt.set_overlay(True)
        from ui.overlay_app import get_overlay_controller

        ctrl = get_overlay_controller()
        ctrl.set_enabled(True, runtime=rt)
        ctrl.ensure_started()
    except Exception:
        pass


def hide_overlay_window(*, reason: str = "") -> None:
    """Hide HUD window without disabling overlay subsystem."""
    global _overlay_window_visible
    del reason
    _overlay_window_visible = False
    try:
        from ui.overlay_app import get_overlay_controller

        get_overlay_controller()._state.hide()
    except Exception:
        pass


def hide_overlay_after_auto_hide() -> None:
    if is_quiet_mode():
        hide_overlay_window(reason="auto_hide")


def reveal_overlay_for_wake() -> None:
    if OVERLAY_SHOW_ON_WAKE or is_quiet_mode():
        show_overlay_window(reason="wake")


def on_explicit_command(command_text: str) -> None:
    """Show overlay for user-initiated commands (not hide/toggle quiet)."""
    text = (command_text or "").strip().lower()
    if text in _HIDDEN_COMMANDS:
        return
    if is_quiet_mode() or BACKGROUND_MODE:
        show_overlay_window(reason="command")


def toggle_quiet_mode() -> bool:
    set_quiet_mode(not is_quiet_mode())
    if is_quiet_mode():
        hide_overlay_window(reason="toggle_on")
    else:
        show_overlay_window(reason="toggle_off")
    return is_quiet_mode()


def quiet_mode_status_line() -> str:
    return (
        f"quiet_mode: {'on' if is_quiet_mode() else 'off'} | "
        f"overlay_visible: {'yes' if is_overlay_window_visible() else 'no'}"
    )
