"""Desktop control runtime facade (Phase 63)."""

from __future__ import annotations

import re
import threading
import time
from typing import Any

import config
from desktop.memory import add_ui_transition, set_active_workflow, set_current_task
from desktop.state import DesktopRuntimeState
from desktop.vision_runtime import (
    _record_action,
    detect_active_app,
    find_button_region,
    get_desktop_state,
)

_RISKY_TOKENS = (
    "delete",
    "remove",
    "submit",
    "buy",
    "purchase",
    "send",
    "login",
    "sign in",
    "password",
    "credential",
    "pay",
    "confirm payment",
)


def _needs_approval(action: str, target: str = "") -> bool:
    text = f"{action} {target}".lower()
    return any(tok in text for tok in _RISKY_TOKENS)


def _approval_message(action: str, target: str = "") -> str:
    return (
        "Approval required before risky desktop action.\n"
        f"  action: {action}\n"
        f"  target: {target or 'n/a'}\n"
        "  blocked: destructive click, credential entry, messaging, file change, or purchase."
    )


def _ensure_control_enabled() -> None:
    from computer_control.safety import ensure_control_enabled

    ensure_control_enabled()


def _ensure_desktop_operator_enabled() -> None:
    if not getattr(config, "DESKTOP_OPERATOR_ENABLED", True):
        raise RuntimeError(
            "Desktop operator is disabled. Set DESKTOP_OPERATOR_ENABLED=true."
        )


def _safe_mode() -> bool:
    return bool(getattr(config, "DESKTOP_OPERATOR_SAFE_MODE", True))


def _state() -> DesktopRuntimeState:
    return get_desktop_state()


def mouse_move(x: int, y: int) -> str:
    _ensure_desktop_operator_enabled()
    _ensure_control_enabled()
    if _safe_mode() and _needs_approval("mouse_move", f"{x},{y}"):
        return _approval_message("mouse_move", f"{x},{y}")
    import pyautogui

    pyautogui.moveTo(int(x), int(y), duration=0.15)
    _record_action("mouse_move", f"{x},{y}")
    add_ui_transition("mouse_move", f"{x},{y}")
    return f"Moved mouse to ({x}, {y})."


def mouse_click(x: int | None = None, y: int | None = None, *, button: str = "left") -> str:
    _ensure_desktop_operator_enabled()
    _ensure_control_enabled()
    target = f"{x},{y} {button}" if x is not None and y is not None else button
    if _safe_mode() and _needs_approval("mouse_click", target):
        return _approval_message("mouse_click", target)
    import pyautogui

    if x is not None and y is not None:
        pyautogui.click(int(x), int(y), button=button)
    else:
        pyautogui.click(button=button)
    _record_action("mouse_click", target)
    add_ui_transition("mouse_click", target)
    return f"Clicked ({target})."


def type_text(text: str, *, approved: bool = False) -> str:
    _ensure_desktop_operator_enabled()
    _ensure_control_enabled()
    payload = (text or "").strip()
    if not payload:
        return "Type command requires non-empty text."
    if _safe_mode() and not approved and _needs_approval("type_text", payload):
        return _approval_message("type_text", payload[:120])
    import pyautogui

    pyautogui.write(payload, interval=0.02)
    _record_action("type_text", payload[:120])
    add_ui_transition("type_text", payload[:120])
    set_current_task(f"typed:{payload[:80]}")
    return f"Typed text ({len(payload)} chars)."


def press_hotkey(*keys: str) -> str:
    _ensure_desktop_operator_enabled()
    _ensure_control_enabled()
    combo = "+".join(k.strip() for k in keys if k.strip())
    if not combo:
        return "Hotkey requires at least one key."
    if _safe_mode() and _needs_approval("hotkey", combo):
        return _approval_message("hotkey", combo)
    import pyautogui

    pyautogui.hotkey(*[k.strip() for k in keys if k.strip()])
    _record_action("hotkey", combo)
    add_ui_transition("hotkey", combo)
    return f"Pressed hotkey: {combo}"


def focus_window(name: str) -> str:
    _ensure_desktop_operator_enabled()
    from computer_control.desktop_controller import focus_application

    body = focus_application(name)
    detect_active_app()
    _record_action("focus_window", name)
    add_ui_transition("focus_window", name)
    return body


def launch_app(name: str) -> str:
    _ensure_desktop_operator_enabled()
    key = (name or "").strip().lower()
    mapping = {
        "chrome": "chrome",
        "discord": "discord",
        "cursor": "cursor",
        "terminal": "terminal",
        "dashboard": "dashboard",
    }
    if key in mapping:
        from computer_control.desktop_controller import open_application

        body = open_application(mapping[key])
        _record_action("launch_app", key)
        set_active_workflow(f"launch:{key}")
        return body
    from actions.app_actions import OpenAppAction
    from core.types import CommandRequest, Intent

    result = OpenAppAction().execute(
        CommandRequest(raw_text=f"open {name}", intent=Intent.OPEN_APP, params={"app": name})
    )
    _record_action("launch_app", key or name)
    return result.summary


def switch_to_chrome() -> str:
    return focus_window("chrome")


def click_button_that_says(label: str, *, approved: bool = False) -> str:
    _ensure_desktop_operator_enabled()
    _ensure_control_enabled()
    target = (label or "").strip()
    if not target:
        return "Provide button label text, e.g. click the button that says OK"
    if _safe_mode() and not approved and _needs_approval("click_button", target):
        return _approval_message("click_button", target)

    match = find_button_region(target)
    if not match:
        return f"No on-screen match found for button text: {target!r}"
    center = match.get("center")
    if not center or len(center) != 2:
        return f"Found '{target}' but no clickable coordinates (OCR region only)."
    x, y = int(center[0]), int(center[1])
    return mouse_click(x, y)


def extract_type_text(raw: str) -> str:
    text = (raw or "").strip()
    patterns = [
        r"^type\s+this\s+(.+)$",
        r"^type\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def extract_button_label(raw: str) -> str:
    text = (raw or "").strip()
    patterns = [
        r"click\s+the\s+button\s+that\s+says\s+(.+)$",
        r"click\s+button\s+(.+)$",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


_lock = threading.RLock()


def recover_desktop_operator() -> tuple[bool, str]:
    """Reset desktop operator transient state and recapture screen."""
    with _lock:
        try:
            from desktop.vision_runtime import capture_active_monitor, detect_active_app, get_desktop_state

            detect_active_app()
            ok_cap, cap_path, _cap_msg = capture_active_monitor()
            st = get_desktop_state()
            _record_action("recover_desktop_operator", "state refreshed")
            add_ui_transition("recover_desktop_operator", st.focused_window or "n/a")
            if ok_cap and cap_path:
                return True, f"Desktop operator recovered; recaptured {cap_path}"
            return True, "Desktop operator state recovered."
        except Exception as exc:
            return False, f"Desktop recovery failed: {exc}"[:200]
