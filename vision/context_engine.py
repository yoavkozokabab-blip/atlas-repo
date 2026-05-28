"""Vision + context awareness (Phase 50)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ROOT
from core.logger import setup_logger

logger = setup_logger("jarvis.vision.context")

CONTEXT_REPORT_DIR = PROJECT_ROOT / "reports" / "context_memory"


def _save_context(event: str, payload: dict) -> str:
    CONTEXT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = CONTEXT_REPORT_DIR / f"{ts}_{event}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)


def _screen_summary() -> dict:
    try:
        from vision.screen_understanding import describe_screen_v35

        return describe_screen_v35()
    except Exception:
        from vision.screen_analyzer import describe_screen

        return describe_screen()


def _active_app() -> str:
    try:
        from computer_control.app_focus import get_focused_app

        info = get_focused_app()
        return info.title or "(unknown)"
    except Exception:
        return "(unavailable)"


def what_am_i_looking_at() -> str:
    data = _screen_summary()
    app = _active_app()
    summary = data.get("summary") or data.get("text_preview") or "No screen summary available."
    _save_context("what_am_i_looking_at", {"app": app, "summary": summary[:500]})
    return f"Active app: {app}\nLooking at:\n{summary}"


def summarize_current_screen() -> str:
    from vision.screen_system import capture_and_summarize_screen

    summary = capture_and_summarize_screen()
    _save_context("summarize_current_screen", {"summary": summary[:500]})
    return summary


def explain_visible_error() -> str:
    try:
        from vision.screen_analyzer import detect_screen_errors

        data = detect_screen_errors()
    except Exception as exc:
        return f"Error detection unavailable: {exc}"
    errors = data.get("errors") or data.get("matches") or []
    if not errors:
        return "No obvious errors detected on current screen."
    lines = ["Visible errors/warnings:"]
    for item in errors[:10]:
        lines.append(f"  - {item}")
    _save_context("explain_visible_error", {"count": len(errors)})
    return "\n".join(lines)


def inspect_current_chart() -> str:
    data = _screen_summary()
    text = (data.get("text") or data.get("ocr_text") or data.get("summary") or "").lower()
    hints = []
    for token in ("chart", "candle", "price", "volume", "tradingview", "symbol"):
        if token in text:
            hints.append(token)
    if not hints:
        return "No chart-like content detected on screen."
    return f"Chart-like content detected: {', '.join(hints)}\nPreview:\n{(data.get('summary') or '')[:400]}"


def summarize_current_report() -> str:
    data = _screen_summary()
    text = data.get("summary") or ""
    if not any(k in text.lower() for k in ("report", "summary", "backtest", "live", "execution")):
        return "Current screen does not appear to show a report view."
    return f"Report-like screen content:\n{text[:800]}"


def continue_previous_investigation() -> str:
    from memory.task_memory import get_last_investigation, resume_last_task

    last = get_last_investigation()
    if not last:
        return "No previous investigation recorded. Try show recent investigations."
    resume = resume_last_task()
    return f"Continuing investigation: {last}\n{resume}"
