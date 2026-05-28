"""Predefined window actions (title match only, no pixel-based targeting)."""

from __future__ import annotations

from computer_control.models import DetailedWindowInfo, WindowActionResult
from computer_control.safety import (
    ensure_control_enabled,
    is_eligible_window,
    is_sensitive_title,
)


def _iter_pygetwindows():
    import pygetwindow as gw

    return gw.getAllWindows()


def _to_detailed(win) -> DetailedWindowInfo:
    title = getattr(win, "title", "") or ""
    width = int(getattr(win, "width", 0) or 0)
    height = int(getattr(win, "height", 0) or 0)
    minimized = bool(getattr(win, "isMinimized", False))
    eligible, reason = is_eligible_window(title, width, height, minimized=minimized)
    return DetailedWindowInfo(
        title=title,
        left=int(getattr(win, "left", 0) or 0),
        top=int(getattr(win, "top", 0) or 0),
        width=width,
        height=height,
        visible=not minimized,
        minimized=minimized,
        eligible=eligible,
        blocked_reason=reason,
    )


def list_windows_detailed(*, limit: int = 40) -> list[DetailedWindowInfo]:
    ensure_control_enabled()
    results: list[DetailedWindowInfo] = []
    try:
        for win in _iter_pygetwindows():
            info = _to_detailed(win)
            if not info.title.strip():
                continue
            results.append(info)
            if len(results) >= limit:
                break
    except Exception as exc:
        return [
            DetailedWindowInfo(
                title="",
                left=0,
                top=0,
                width=0,
                height=0,
                visible=False,
                minimized=False,
                eligible=False,
                blocked_reason=str(exc),
            )
        ]
    return results


def _find_eligible_by_title(query: str) -> list:
    q = (query or "").strip().lower()
    if not q:
        return []
    matches = []
    for win in _iter_pygetwindows():
        title = (getattr(win, "title", "") or "").strip()
        if not title or q not in title.lower():
            continue
        width = int(getattr(win, "width", 0) or 0)
        height = int(getattr(win, "height", 0) or 0)
        minimized = bool(getattr(win, "isMinimized", False))
        eligible, _ = is_eligible_window(title, width, height, minimized=minimized)
        if eligible:
            matches.append(win)
    return matches


def _resolve_single_window(title_query: str) -> tuple[object | None, WindowActionResult]:
    if is_sensitive_title(title_query):
        return None, WindowActionResult(
            success=False,
            message="Cannot act on windows with sensitive titles.",
        )

    matches = _find_eligible_by_title(title_query)
    titles = [(getattr(w, "title", "") or "") for w in matches]

    if not matches:
        return None, WindowActionResult(
            success=False,
            message=f"No eligible window matched '{title_query}'.",
            candidates=[],
        )
    if len(matches) > 1:
        return None, WindowActionResult(
            success=False,
            message=f"Multiple windows match '{title_query}'. Be more specific.",
            candidates=titles[:10],
            ambiguous=True,
        )

    win = matches[0]
    return win, WindowActionResult(
        success=True,
        message="Single match found.",
        matched_title=getattr(win, "title", "") or "",
    )


def focus_window(title_query: str) -> WindowActionResult:
    ensure_control_enabled()
    win, result = _resolve_single_window(title_query)
    if not result.success:
        return result
    try:
        win.activate()
        return WindowActionResult(
            success=True,
            message=f"Focused window: {result.matched_title}",
            matched_title=result.matched_title,
        )
    except Exception as exc:
        return WindowActionResult(
            success=False,
            message=f"Could not focus window: {exc}",
            matched_title=result.matched_title,
        )


def minimize_window(title_query: str) -> WindowActionResult:
    ensure_control_enabled()
    win, result = _resolve_single_window(title_query)
    if not result.success:
        return result
    try:
        win.minimize()
        return WindowActionResult(
            success=True,
            message=f"Minimized window: {result.matched_title}",
            matched_title=result.matched_title,
        )
    except Exception as exc:
        return WindowActionResult(
            success=False,
            message=f"Could not minimize window: {exc}",
            matched_title=result.matched_title,
        )


def maximize_window(title_query: str) -> WindowActionResult:
    ensure_control_enabled()
    win, result = _resolve_single_window(title_query)
    if not result.success:
        return result
    try:
        win.maximize()
        return WindowActionResult(
            success=True,
            message=f"Maximized window: {result.matched_title}",
            matched_title=result.matched_title,
        )
    except Exception as exc:
        return WindowActionResult(
            success=False,
            message=f"Could not maximize window: {exc}",
            matched_title=result.matched_title,
        )
