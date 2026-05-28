"""Phase 35 — active window metadata (read-only, no control)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import SCREEN_BLOCKED_WINDOW_KEYWORDS, SCREEN_BLOCK_SECRET_WINDOWS
from core.logger import setup_logger

logger = setup_logger("jarvis.vision.active_window")


@dataclass
class ActiveWindowMeta:
    title: str = ""
    process_name: str = ""
    pid: int | None = None
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    is_blocked: bool = False
    block_reason: str = ""
    warning: str = ""
    error: str | None = None


def _blocked_keywords() -> list[str]:
    raw = SCREEN_BLOCKED_WINDOW_KEYWORDS or ""
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def _check_blocked(title: str, process_name: str) -> tuple[bool, str]:
    if not SCREEN_BLOCK_SECRET_WINDOWS:
        return False, ""
    blob = f"{title} {process_name}".lower()
    for kw in _blocked_keywords():
        if kw and kw in blob:
            return True, f"Blocked keyword in window context: '{kw}'"
    return False, ""


def _from_pygetwindow() -> ActiveWindowMeta:
    try:
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is None:
            return ActiveWindowMeta(error="No active window detected.")
        title = getattr(win, "title", "") or ""
        meta = ActiveWindowMeta(
            title=title,
            left=int(getattr(win, "left", 0) or 0),
            top=int(getattr(win, "top", 0) or 0),
            width=int(getattr(win, "width", 0) or 0),
            height=int(getattr(win, "height", 0) or 0),
        )
        blocked, reason = _check_blocked(title, "")
        meta.is_blocked = blocked
        meta.block_reason = reason
        return meta
    except Exception as exc:
        return ActiveWindowMeta(error=str(exc), warning="pygetwindow unavailable")


def _enrich_win32(meta: ActiveWindowMeta) -> ActiveWindowMeta:
    try:
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return meta
        title = win32gui.GetWindowText(hwnd) or meta.title
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = ""
        try:
            import psutil

            process_name = psutil.Process(pid).name()
        except Exception:
            process_name = ""
        rect = win32gui.GetWindowRect(hwnd)
        meta.title = title
        meta.pid = pid
        meta.process_name = process_name
        meta.left, meta.top, meta.width, meta.height = (
            rect[0],
            rect[1],
            max(0, rect[2] - rect[0]),
            max(0, rect[3] - rect[1]),
        )
        blocked, reason = _check_blocked(title, process_name)
        meta.is_blocked = blocked
        meta.block_reason = reason
    except ImportError:
        if not meta.warning:
            meta.warning = "win32/pywin32 not available for process metadata"
    except Exception as exc:
        meta.warning = f"win32 metadata degraded: {exc}"
    return meta


def get_active_window_metadata() -> ActiveWindowMeta:
    """Best-effort active window info with secret-window blocking."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return ActiveWindowMeta(
            title="(pytest)",
            process_name="pytest",
            warning="Active window skipped during tests",
        )
    meta = _from_pygetwindow()
    if meta.error and not meta.title:
        return meta
    return _enrich_win32(meta)
