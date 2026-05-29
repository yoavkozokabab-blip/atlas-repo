"""Desktop vision runtime facade (Phase 63)."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from config import DATA_DIR, SCREEN_UNDERSTANDING_ENABLED
from core.file_cleanup import remove_file_best_effort
from desktop.memory import add_recent_screen, add_ui_transition
from desktop.state import DesktopRuntimeState

_SCREENSHOT_DIR = DATA_DIR / "desktop_screenshots"
_MAX_DESKTOP_SCREENSHOTS = 10
_MOCK_BANNER = "SIMULATED DESKTOP VISION | NO REAL CAPTURE"
_REAL_BANNER = "REAL DESKTOP VISION"

_state = DesktopRuntimeState()
_lock = threading.RLock()


@dataclass
class ScreenUnderstanding:
    title: str = ""
    active_app: str = ""
    visible_buttons: list[str] = field(default_factory=list)
    menus: list[str] = field(default_factory=list)
    text_blocks: list[str] = field(default_factory=list)
    dialogs: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    taskbar_apps: list[str] = field(default_factory=list)
    screenshot_path: str = ""
    ocr_excerpt: str = ""
    regions: list[dict[str, Any]] = field(default_factory=list)


def get_desktop_state() -> DesktopRuntimeState:
    with _lock:
        return DesktopRuntimeState(**_state.__dict__)


def _mode_banner(real: bool) -> str:
    return _REAL_BANNER if real else _MOCK_BANNER


def _record_action(action: str, detail: str = "", *, success: bool = True) -> None:
    row = f"{action}: {detail}"[:300]
    _state.recent_actions.append(row)
    _state.recent_actions = _state.recent_actions[-50:]
    _state.last_action_success = success
    _state.last_updated_ts = time.time()
    add_ui_transition(action, detail)


def _prune_screenshot_count() -> None:
    """Keep only the newest desktop screenshots."""
    try:
        files = sorted(
            _SCREENSHOT_DIR.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for old in files[_MAX_DESKTOP_SCREENSHOTS:]:
        remove_file_best_effort(old, attempts=2)


def capture_active_monitor() -> tuple[bool, str, str]:
    """Capture primary monitor; returns (ok, path, message)."""
    with _lock:
        if not SCREEN_UNDERSTANDING_ENABLED:
            _state.last_exception = "screen understanding disabled"
            _record_action("capture_active_monitor", "disabled", success=False)
            return False, "", f"{_MOCK_BANNER}\nScreen understanding disabled."
        try:
            from vision.screen_capture import safe_capture_screen

            capture = safe_capture_screen(mode="full_screen")
            if not capture.ok or capture.image is None:
                _state.last_exception = capture.error or capture.warning or "capture failed"
                _record_action("capture_active_monitor", _state.last_exception, success=False)
                return False, "", f"Capture failed: {_state.last_exception}"
            _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            path = _SCREENSHOT_DIR / f"desktop_{int(time.time() * 1000)}.png"
            capture.image.save(path, format="PNG")
            _prune_screenshot_count()
            _state.last_screenshot_path = str(path)
            _record_action("capture_active_monitor", str(path))
            return True, str(path), f"{_REAL_BANNER}\nCaptured active monitor: {path}"
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
            _record_action("capture_active_monitor", _state.last_exception, success=False)
            return False, "", f"Capture failed: {_state.last_exception}"


def detect_windows() -> list[dict[str, str]]:
    with _lock:
        rows: list[dict[str, str]] = []
        try:
            from vision.window_info import list_visible_windows

            for win in list_visible_windows():
                if win.error and not win.title:
                    continue
                rows.append(
                    {
                        "title": (win.title or "")[:180],
                        "width": str(win.width),
                        "height": str(win.height),
                        "state": "minimized" if win.minimized else "visible",
                    }
                )
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
        _state.open_window_count = len(rows)
        return rows


def detect_active_app() -> str:
    with _lock:
        try:
            from vision.active_window import get_active_window_metadata

            meta = get_active_window_metadata()
            app = meta.process_name or meta.title or "unknown"
            _state.active_app = app
            _state.focused_window = meta.title or ""
            return app
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
            return ""


def extract_ocr_text() -> tuple[str, str]:
    """Returns (text, engine). Uses Phase 67 fallback pipeline when needed."""
    with _lock:
        if not SCREEN_UNDERSTANDING_ENABLED:
            return "", "disabled"
        try:
            from desktop.ocr_pipeline import extract_ocr_with_fallback

            path = _state.last_screenshot_path
            if not path:
                capture_active_monitor()
                path = _state.last_screenshot_path
            text, engine, diag = extract_ocr_with_fallback(screenshot_path=path or "")
            _state.last_ocr_excerpt = text[:2000]
            if diag.screenshot_path:
                _state.last_screenshot_path = diag.screenshot_path
            return text, engine
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
            return "", "error"


def select_screen_region(x: int, y: int, width: int, height: int) -> dict[str, int]:
    with _lock:
        region = {
            "x": max(0, int(x)),
            "y": max(0, int(y)),
            "width": max(1, int(width)),
            "height": max(1, int(height)),
        }
        _record_action("select_screen_region", f"{region}")
        return region


def _classify_ui_elements(lines: list[str]) -> ScreenUnderstanding:
    buttons: list[str] = []
    menus: list[str] = []
    dialogs: list[str] = []
    notifications: list[str] = []
    taskbar: list[str] = []
    text_blocks: list[str] = []

    menu_words = ("file", "edit", "view", "tools", "help", "settings")
    dialog_words = ("dialog", "confirm", "warning", "error", "are you sure")
    notify_words = ("notification", "alert", "reminder", "update available")
    button_words = (
        "ok",
        "cancel",
        "save",
        "submit",
        "close",
        "apply",
        "delete",
        "buy",
        "send",
        "login",
        "sign in",
        "continue",
        "next",
        "search",
    )

    for line in lines[:120]:
        low = line.lower().strip()
        if not low:
            continue
        if len(low) > 8:
            text_blocks.append(line[:220])
        if any(w in low for w in menu_words) and len(low) < 40:
            menus.append(line[:120])
        if any(w in low for w in dialog_words):
            dialogs.append(line[:160])
        if any(w in low for w in notify_words):
            notifications.append(line[:160])
        if "taskbar" in low or "start" == low:
            taskbar.append(line[:120])
        for word in button_words:
            if re.search(rf"\b{re.escape(word)}\b", low):
                buttons.append(line[:120])
                break

    return ScreenUnderstanding(
        visible_buttons=buttons[:30],
        menus=menus[:20],
        text_blocks=text_blocks[:40],
        dialogs=dialogs[:15],
        notifications=notifications[:15],
        taskbar_apps=taskbar[:15],
    )


def understand_screen() -> ScreenUnderstanding:
    with _lock:
        app = detect_active_app()
        text, _engine = extract_ocr_text()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        model = _classify_ui_elements(lines)
        model.title = _state.focused_window
        model.active_app = app
        model.ocr_excerpt = text[:2500]
        model.screenshot_path = _state.last_screenshot_path
        return model


def what_is_on_my_screen() -> str:
    with _lock:
        if not SCREEN_UNDERSTANDING_ENABLED:
            return f"{_MOCK_BANNER}\nScreen understanding disabled."
        try:
            from vision.screen_understanding import describe_screen_v35

            data = describe_screen_v35()
            summary = str(data.get("summary") or "No screen summary.")
            _state.last_screen_summary = summary[:3000]
            detect_active_app()
            detect_windows()
            model = understand_screen()
            _record_action("what_is_on_my_screen", _state.focused_window)
            add_recent_screen(summary, _state.last_screenshot_path, _state.active_app)
            lines = [
                _REAL_BANNER,
                summary,
                f"  active_app: {_state.active_app or 'n/a'}",
                f"  open_windows: {_state.open_window_count}",
                f"  visible_buttons: {len(model.visible_buttons)}",
                f"  menus: {len(model.menus)}",
                f"  dialogs: {len(model.dialogs)}",
            ]
            return "\n".join(lines)
        except Exception as exc:
            _state.last_exception = str(exc)[:300]
            _record_action("what_is_on_my_screen", _state.last_exception, success=False)
            return f"Screen description failed: {_state.last_exception}"


def summarize_this_screen() -> str:
    with _lock:
        body = what_is_on_my_screen()
        model = understand_screen()
        excerpt = (model.ocr_excerpt or "")[:500]
        summary = (
            f"Screen summary:\n"
            f"  app: {model.active_app or 'n/a'}\n"
            f"  window: {model.title or 'n/a'}\n"
            f"  text_excerpt: {excerpt or 'n/a'}\n"
            f"  buttons_detected: {len(model.visible_buttons)}\n"
            f"  notifications: {len(model.notifications)}"
        )
        _state.last_screen_summary = summary
        _state.screen_summaries.append(summary)
        _state.screen_summaries = _state.screen_summaries[-30:]
        add_recent_screen(summary, _state.last_screenshot_path, _state.active_app)
        return f"{body}\n\n{summary}"


def take_screenshot() -> str:
    ok, path, msg = capture_active_monitor()
    if not ok:
        return msg
    _record_action("take_screenshot", path)
    return msg


def list_open_windows() -> str:
    with _lock:
        try:
            from computer_control.desktop_controller import show_open_windows

            body = show_open_windows()
        except Exception:
            windows = detect_windows()
            lines = [f"Open windows ({len(windows)}):"]
            for row in windows[:30]:
                lines.append(f"  - {row.get('title', 'n/a')} ({row.get('state', 'unknown')})")
            body = "\n".join(lines)
        detect_active_app()
        _record_action("list_open_windows", f"count={_state.open_window_count}")
        return f"{_REAL_BANNER}\n{body}"


def find_button_region(label: str) -> dict[str, Any] | None:
    q = (label or "").strip()
    if not q:
        return None
    from vision.screen_understanding import find_on_screen_v35

    data = find_on_screen_v35(q)
    matches = data.get("matches") or []
    if not matches:
        return None
    first = matches[0]
    region = first.get("region") or {}
    center = region.get("center")
    if not center:
        return None
    return {"label": q, "center": center, "match": first.get("match", "")}
