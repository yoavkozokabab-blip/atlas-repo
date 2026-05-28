"""High-level read-only screen analysis."""

from __future__ import annotations

import re
from typing import Any

from config import VISION_MAX_OCR_CHARS
from vision.ocr import OCRResult, extract_text
from vision.redaction import redact_sensitive_text
from vision.screen_capture import (
    VisionDisabledError,
    capture_screen,
    cleanup_temp,
)
from vision.window_info import get_active_window_info, list_visible_windows

_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\berror\b", re.I), "error"),
    (re.compile(r"\bexception\b", re.I), "exception"),
    (re.compile(r"\btraceback\b", re.I), "traceback"),
    (re.compile(r"\bfailed\b", re.I), "failed"),
    (re.compile(r"\bwarning\b", re.I), "warning"),
    (re.compile(r"\bcannot\b", re.I), "cannot"),
    (re.compile(r"\bdenied\b", re.I), "denied"),
    (re.compile(r"\brefused\b", re.I), "refused"),
    (re.compile(r"\bdisconnected\b", re.I), "disconnected"),
    (re.compile(r"שגיאה"), "שגיאה"),
    (re.compile(r"נכשל"), "נכשל"),
    (re.compile(r"אזהרה"), "אזהרה"),
    (re.compile(r"נדחה"), "נדחה"),
    (re.compile(r"חסום"), "חסום"),
    (re.compile(r"אין גישה"), "אין גישה"),
]


def _infer_app(title: str, ocr_sample: str) -> str:
    combined = f"{title} {ocr_sample}".lower()
    hints = [
        ("cursor", "Cursor IDE"),
        ("visual studio code", "VS Code"),
        ("chrome", "Chrome"),
        ("firefox", "Firefox"),
        ("powershell", "PowerShell"),
        ("cmd.exe", "Command Prompt"),
        ("trading", "Trading dashboard"),
        ("excel", "Excel"),
        ("outlook", "Outlook"),
    ]
    for key, label in hints:
        if key in combined:
            return label
    if title.strip():
        return f"Window: {title[:80]}"
    return "Unknown application"


def _ocr_from_capture(save: bool = False) -> tuple[OCRResult, Any, dict[str, Any]]:
    shot = capture_screen(save=save)
    meta: dict[str, Any] = {
        "width": shot.width,
        "height": shot.height,
        "monitor": shot.monitor,
        "saved_path": str(shot.saved_path) if shot.saved_path else None,
        "temporary": shot.saved_path is None,
    }
    if shot.error:
        return OCRResult(error=shot.error), shot.image, meta

    ocr = extract_text(shot.image)
    cleanup_temp(shot.temp_path)
    return ocr, shot.image, meta


def describe_screen() -> dict[str, Any]:
    active = get_active_window_info()
    windows = list_visible_windows(limit=10)
    ocr, _, meta = _ocr_from_capture(save=False)

    top_lines = ocr.lines[:12] if ocr.lines else []
    if ocr.text and not top_lines:
        top_lines = ocr.text.splitlines()[:12]
    redacted_lines = [redact_sensitive_text(ln) for ln in top_lines]

    win_summaries = []
    for w in windows[:8]:
        if w.error:
            continue
        flag = "minimized" if w.minimized else "visible"
        win_summaries.append(f"{w.title[:60]} ({w.width}x{w.height}, {flag})")

    likely = _infer_app(active.title, " ".join(redacted_lines[:5]))

    summary_parts = [
        f"Active window: {active.title or '(unknown)'}",
        f"Likely app: {likely}",
        f"Capture: {meta.get('width')}x{meta.get('height')}",
    ]
    if win_summaries:
        summary_parts.append("Visible windows: " + "; ".join(win_summaries[:5]))
    if redacted_lines:
        summary_parts.append("OCR preview:")
        summary_parts.extend(f"  - {ln}" for ln in redacted_lines[:8])
    elif ocr.error:
        summary_parts.append(f"OCR: {ocr.error}")
    else:
        summary_parts.append("OCR: little or no text detected.")

    return {
        "summary": "\n".join(summary_parts),
        "active_window": active.__dict__,
        "visible_windows": [w.__dict__ for w in windows if not w.error],
        "ocr_lines": redacted_lines,
        "likely_app": likely,
        "capture": meta,
        "ocr_error": ocr.error,
    }


def read_screen_text() -> dict[str, Any]:
    ocr, _, meta = _ocr_from_capture(save=False)
    if ocr.error and not ocr.text:
        return {"summary": f"Could not read screen text: {ocr.error}", "text": "", "ocr": ocr.__dict__}

    text = redact_sensitive_text(ocr.text)
    if len(text) > VISION_MAX_OCR_CHARS:
        text = text[: VISION_MAX_OCR_CHARS - 3] + "..."

    line_count = len(ocr.lines)
    summary = f"Read {line_count} OCR lines ({len(text)} chars, redacted)."
    if ocr.error:
        summary += f" Note: {ocr.error}"

    return {
        "summary": summary,
        "text": text,
        "lines": [redact_sensitive_text(ln) for ln in ocr.lines[:200]],
        "ocr": {
            "confidence": ocr.confidence,
            "language": ocr.language,
            "error": ocr.error,
        },
        "capture": meta,
    }


def detect_screen_errors() -> dict[str, Any]:
    ocr, _, meta = _ocr_from_capture(save=False)
    matches: list[dict[str, str]] = []

    for line in ocr.lines:
        redacted = redact_sensitive_text(line)
        for pat, label in _ERROR_PATTERNS:
            if pat.search(redacted):
                matches.append({"line": redacted, "pattern": label})
                break

    if not matches and ocr.text:
        for line in ocr.text.splitlines():
            redacted = redact_sensitive_text(line.strip())
            if not redacted:
                continue
            for pat, label in _ERROR_PATTERNS:
                if pat.search(redacted):
                    matches.append({"line": redacted, "pattern": label})
                    break

    if matches:
        summary = f"Found {len(matches)} possible error line(s) on screen."
    elif ocr.error:
        summary = f"No error lines detected (OCR issue: {ocr.error})."
    else:
        summary = "No error-like lines detected on screen."

    return {
        "summary": summary,
        "matches": matches[:50],
        "match_count": len(matches),
        "ocr_error": ocr.error,
        "capture": meta,
    }


def take_screenshot_data(*, save: bool | None = None) -> dict[str, Any]:
    do_save = bool(save)
    shot = capture_screen(save=do_save)
    if shot.error:
        return {"summary": f"Screenshot failed: {shot.error}", "saved": False}

    cleanup_temp(shot.temp_path)
    if shot.saved_path:
        summary = f"Screenshot saved under capture dir ({shot.width}x{shot.height})."
        saved = True
        path_str = str(shot.saved_path)
    else:
        summary = (
            f"Screenshot captured in memory only ({shot.width}x{shot.height}). "
            "Not saved (VISION_SAVE_SCREENSHOTS=false)."
        )
        saved = False
        path_str = None

    return {
        "summary": summary,
        "saved": saved,
        "path": path_str,
        "width": shot.width,
        "height": shot.height,
        "monitor": shot.monitor,
    }
