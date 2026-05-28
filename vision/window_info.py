"""Active and visible window metadata (read-only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.vision.windows")


@dataclass
class WindowInfo:
    title: str = ""
    process: str | None = None
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    minimized: bool = False
    error: str | None = None


def _from_pygetwindow(win) -> WindowInfo:
    return WindowInfo(
        title=getattr(win, "title", "") or "",
        left=int(getattr(win, "left", 0) or 0),
        top=int(getattr(win, "top", 0) or 0),
        width=int(getattr(win, "width", 0) or 0),
        height=int(getattr(win, "height", 0) or 0),
        visible=not bool(getattr(win, "isMinimized", False)),
        minimized=bool(getattr(win, "isMinimized", False)),
    )


def get_active_window_info() -> WindowInfo:
    try:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is None:
            return WindowInfo(error="No active window detected.")
        return _from_pygetwindow(win)
    except Exception as exc:
        logger.debug("get_active_window_info: %s", exc)
        return WindowInfo(error=str(exc))


def list_visible_windows(*, limit: int = 25) -> list[WindowInfo]:
    try:
        import pygetwindow as gw

        windows: list[WindowInfo] = []
        for win in gw.getAllWindows():
            info = _from_pygetwindow(win)
            if not info.title.strip():
                continue
            if info.width <= 0 and info.height <= 0:
                continue
            windows.append(info)
            if len(windows) >= limit:
                break
        return windows
    except Exception as exc:
        logger.debug("list_visible_windows: %s", exc)
        return [WindowInfo(error=str(exc))]
