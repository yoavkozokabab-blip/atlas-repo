"""Safe desktop control layer (Phase 50)."""

from __future__ import annotations

import os
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT, TRADING_DASHBOARD_URL, TRADING_REPORTS_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.computer_control.desktop")

DESKTOP_REPORT_DIR = PROJECT_ROOT / "reports" / "desktop_control"


def _audit(action: str, detail: str) -> str:
    DESKTOP_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = DESKTOP_REPORT_DIR / f"{ts}_{action.replace(' ', '_')}.json"
    path.write_text(
        f'{{"action":"{action}","detail":"{detail[:300]}","ts":"{datetime.now(timezone.utc).isoformat()}"}}',
        encoding="utf-8",
    )
    return str(path)


def open_application(name: str) -> str:
    key = (name or "").strip().lower()
    mapping = {
        "chrome": ("open_chrome", "chrome"),
        "cursor": ("open_cursor", "cursor"),
        "dashboard": ("open_trading_dashboard", TRADING_DASHBOARD_URL),
        "terminal": ("open_terminal", "wt"),
    }
    if key not in mapping:
        return f"Application {name!r} not in allowlist. Supported: {', '.join(mapping)}"
    action, target = mapping[key]
    if key == "dashboard":
        from runtime.dashboard_health import mark_dashboard_open_requested

        mark_dashboard_open_requested()
        webbrowser.open(target)
    elif key == "terminal":
        os.startfile("wt")  # noqa: S606 — allowlisted terminal launch on Windows
    elif key == "chrome":
        webbrowser.open("https://www.google.com/chrome/")
    else:
        webbrowser.open("cursor://")
    report = _audit(action, target)
    return f"Opened {key}. audit={report}"


def focus_application(name: str) -> str:
    from computer_control.window_actions import focus_window

    title = (name or "").strip()
    if not title:
        return "Focus requires an application/window name."
    result = focus_window(title)
    report = _audit("focus_application", title)
    if not result.success:
        return f"Focus failed: {result.message} audit={report}"
    return f"Focused window matching {title!r}. audit={report}"


def list_open_windows() -> str:
    return show_open_windows()


def show_open_windows() -> str:
    from computer_control.window_actions import list_windows_detailed

    try:
        from computer_control.app_focus import get_focused_app

        focused = get_focused_app().title or ""
    except Exception:
        focused = ""

    windows = list_windows_detailed()
    lines = [f"Open windows ({len(windows)}):"]
    for w in windows[:30]:
        flags = []
        if focused and focused.lower() in (w.title or "").lower():
            flags.append("focused")
        if getattr(w, "minimized", False):
            flags.append("minimized")
        proc = getattr(w, "process_name", "") or getattr(w, "app", "") or "unknown"
        flag_text = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"  - {w.title[:80]} | process={proc}{flag_text}")
    _audit("show_open_windows", f"count={len(windows)}")
    return "\n".join(lines)


def show_focused_window() -> str:
    try:
        from vision.window_info import get_active_window_info

        win = get_active_window_info()
        return "\n".join(
            [
                "Focused window:",
                f"  title: {win.title or '(unknown)'}",
                f"  process: {win.process_name or '(unknown)'}",
                f"  minimized: {getattr(win, 'minimized', False)}",
                f"  size: {win.width}x{win.height}",
            ]
        )
    except Exception as exc:
        return f"Focused window unavailable: {exc}"


def switch_to_browser() -> str:
    return focus_application("chrome")


def switch_to_cursor() -> str:
    return focus_application("cursor")


def switch_to_dashboard() -> str:
    return focus_application("dashboard") + f"\nURL: {TRADING_DASHBOARD_URL}"


def focus_terminal() -> str:
    return focus_application("terminal")


def switch_window(name: str) -> str:
    return focus_application(name)


def open_latest_report() -> str:
    roots = [TRADING_REPORTS_ROOT, PROJECT_ROOT / "reports"]
    candidates: list[Path] = []
    for root in roots:
        if root.exists():
            candidates.extend(root.rglob("*.md"))
            candidates.extend(root.rglob("*.json"))
    if not candidates:
        return "No reports found."
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    os.startfile(latest)  # noqa: S606
    report = _audit("open_latest_report", str(latest))
    return f"Opened latest report: {latest}\naudit={report}"


def search_local_reports(query: str) -> str:
    q = (query or "").strip().lower()
    if not q:
        return "Provide a search term (symbol, date, report name)."
    roots = [TRADING_REPORTS_ROOT, PROJECT_ROOT / "reports"]
    matches: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if q in path.name.lower() or q in str(path).lower():
                matches.append(path)
    matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    if not matches:
        return f"No reports matching {query!r}."
    lines = [f"Reports matching {query!r}:"]
    lines.extend(f"  - {p}" for p in matches)
    _audit("search_local_reports", q)
    return "\n".join(lines)


def take_screenshot_safe() -> str:
    from vision.screen_analyzer import take_screenshot_data

    data = take_screenshot_data()
    path = data.get("path") or data.get("screenshot_path") or "(unknown)"
    _audit("take_screenshot", str(path))
    return f"Screenshot captured: {path}"


def summarize_screen_safe() -> str:
    from vision.context_engine import summarize_current_screen

    return summarize_current_screen()
