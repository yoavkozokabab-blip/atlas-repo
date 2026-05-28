"""Desktop vision / OCR health (Phase 67)."""

from __future__ import annotations

from desktop.ocr_pipeline import extract_ocr_with_fallback, tesseract_installed, windows_ocr_available
from desktop.vision_runtime import capture_active_monitor, get_desktop_state


def show_desktop_vision_health() -> str:
    ok_cap, path, cap_msg = capture_active_monitor()
    text, engine, diag = extract_ocr_with_fallback(screenshot_path=path if ok_cap else "")
    st = get_desktop_state()
    lines = [
        "Desktop vision health",
        f"  screen_understanding_enabled: {bool(__import__('config').SCREEN_UNDERSTANDING_ENABLED)}",
        f"  capture_ok: {ok_cap}",
        f"  screenshot_path: {path or 'n/a'}",
        f"  tesseract_installed: {tesseract_installed()}",
        f"  windows_ocr_available: {windows_ocr_available()}",
        f"  ocr_engine: {engine}",
        f"  ocr_text_length: {diag.text_length}",
        f"  ocr_confidence: {diag.confidence if diag.confidence is not None else 'n/a'}",
        f"  accessibility_fallback_used: {diag.accessibility_fallback_used}",
        f"  active_app: {st.active_app or 'n/a'}",
        f"  open_windows: {st.open_window_count}",
        f"  last_exception: {st.last_exception or 'none'}",
    ]
    if not ok_cap:
        lines.append(f"  capture_note: {cap_msg[:120]}")
    if text.strip():
        lines.append(f"  ocr_excerpt: {text[:120].replace(chr(10), ' ')}")
    return "\n".join(lines)
