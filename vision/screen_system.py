"""Screen capture system diagnostics and resilient summarize (Phase 51)."""

from __future__ import annotations

import importlib.util
from typing import Any


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def probe_screen_system() -> dict[str, Any]:
    mss_ok = _module_available("mss")
    pygetwindow_ok = _module_available("pygetwindow")
    pyautogui_ok = _module_available("pyautogui")
    ocr_ok = _module_available("pytesseract")
    pillow_ok = _module_available("PIL")

    screenshot_capable = mss_ok and pillow_ok
    active_window_capable = pygetwindow_ok or pyautogui_ok

    try:
        from config import SCREEN_OCR_ENABLED, SCREEN_UNDERSTANDING_ENABLED, VISION_ENABLED

        flags = {
            "vision_enabled": VISION_ENABLED,
            "screen_understanding_enabled": SCREEN_UNDERSTANDING_ENABLED,
            "screen_ocr_enabled": SCREEN_OCR_ENABLED,
        }
    except Exception:
        flags = {}

    return {
        "mss_available": mss_ok,
        "pygetwindow_available": pygetwindow_ok,
        "pyautogui_available": pyautogui_ok,
        "ocr_available": ocr_ok and pillow_ok,
        "pillow_available": pillow_ok,
        "screenshot_capability": screenshot_capable,
        "active_window_capability": active_window_capable,
        **flags,
    }


def show_screen_system_status() -> str:
    probe = probe_screen_system()
    lines = [
        "Screen system status:",
        f"  mss available: {probe['mss_available']}",
        f"  pygetwindow available: {probe['pygetwindow_available']}",
        f"  pyautogui available: {probe['pyautogui_available']}",
        f"  OCR available: {probe['ocr_available']}",
        f"  screenshot capability: {probe['screenshot_capability']}",
        f"  active window capability: {probe['active_window_capability']}",
        f"  vision enabled: {probe.get('vision_enabled')}",
        f"  screen understanding enabled: {probe.get('screen_understanding_enabled')}",
    ]
    if not probe["mss_available"]:
        lines.append("  fix: pip install mss Pillow")
    if not probe["pygetwindow_available"]:
        lines.append("  fix: pip install pygetwindow")
    return "\n".join(lines)


def _active_window_meta() -> dict[str, str]:
    title = "(unknown)"
    process = "(unknown)"
    try:
        from vision.window_info import get_active_window_info

        win = get_active_window_info()
        title = win.title or title
        process = win.process_name or process
    except Exception:
        try:
            from computer_control.app_focus import get_focused_app

            info = get_focused_app()
            title = info.title or title
        except Exception:
            pass
    return {"title": title, "process": process}


def capture_and_summarize_screen() -> str:
    probe = probe_screen_system()
    if not probe["screenshot_capability"]:
        return (
            "Screen capture unavailable.\n"
            + show_screen_system_status()
            + "\nInstall: pip install mss Pillow pygetwindow"
        )

    meta = _active_window_meta()
    ocr_text = ""
    summary = ""
    errors: list[str] = []
    charts: list[str] = []
    apps: list[str] = []

    try:
        from vision.screen_capture import capture_active_window, capture_screen
        from config import SCREEN_UNDERSTANDING_ENABLED, VISION_ENABLED

        if VISION_ENABLED or SCREEN_UNDERSTANDING_ENABLED:
            shot = capture_active_window(save=False)
        else:
            shot = capture_screen(save=False)
        if shot.error:
            errors.append(f"capture: {shot.error}")
        else:
            summary = f"Captured {shot.width}x{shot.height} from active region."
    except Exception as exc:
        errors.append(f"capture exception: {exc}")

    try:
        from vision.screen_understanding import describe_screen_v35

        data = describe_screen_v35()
        summary = data.get("summary") or summary
        ocr_text = data.get("ocr_text") or data.get("text_preview") or ""
    except Exception:
        try:
            from vision.screen_analyzer import describe_screen, detect_screen_errors

            data = describe_screen()
            summary = data.get("summary") or summary
            ocr_text = data.get("text") or data.get("ocr_text") or ""
            err_data = detect_screen_errors()
            errors.extend(err_data.get("errors") or err_data.get("matches") or [])
        except Exception as exc:
            errors.append(f"ocr/describe: {exc}")

    lower = (ocr_text or summary or "").lower()
    for token in ("chart", "candle", "tradingview", "log", "error", "warning", "traceback"):
        if token in lower:
            if token in {"chart", "candle", "tradingview"}:
                charts.append(token)
            elif token in {"log", "error", "warning", "traceback"}:
                if token not in errors:
                    errors.append(token)
    if meta["title"] != "(unknown)":
        apps.append(meta["title"])

    lines = [
        "Screen summary:",
        f"  active window: {meta['title']}",
        f"  process: {meta['process']}",
        f"  capture: {summary or 'none'}",
    ]
    if apps:
        lines.append(f"  visible apps: {', '.join(apps[:5])}")
    if charts:
        lines.append(f"  chart hints: {', '.join(sorted(set(charts)))}")
    if errors:
        lines.append("  detected issues:")
        for item in errors[:8]:
            lines.append(f"    - {item}")
    preview = (ocr_text or summary or "")[:600].strip()
    if preview:
        lines.append("  OCR preview:")
        lines.append(f"    {preview}")
    return "\n".join(lines)
