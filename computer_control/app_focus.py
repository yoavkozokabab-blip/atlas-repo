"""Read-only focused application info."""

from __future__ import annotations

from computer_control.models import FocusedAppInfo
from computer_control.safety import ensure_control_enabled


def get_focused_app() -> FocusedAppInfo:
    ensure_control_enabled()
    try:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is None:
            return FocusedAppInfo(title="", error="No focused window detected.")
        title = getattr(win, "title", "") or ""
        return FocusedAppInfo(
            title=title,
            width=int(getattr(win, "width", 0) or 0),
            height=int(getattr(win, "height", 0) or 0),
            minimized=bool(getattr(win, "isMinimized", False)),
        )
    except Exception as exc:
        return FocusedAppInfo(title="", error=str(exc))
