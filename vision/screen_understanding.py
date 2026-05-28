"""Phase 35 — read-only screen understanding orchestration."""

from __future__ import annotations

import re
from typing import Any

import config
from config import (
    SCREEN_CAPTURE_MODE,
    SCREEN_FIND_MAX_RESULTS,
    SCREEN_MAX_TEXT_CHARS,
    SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
)
from vision.active_window import ActiveWindowMeta, get_active_window_metadata
from vision.screen_capture import (
    CaptureResult,
    delete_capture_temp,
    ensure_ocr_temp_path,
    safe_capture_screen,
)
from vision.screen_ocr import OcrBlock, ScreenOcrResult, run_screen_ocr
from vision.screen_redaction import redact_screen_text

_BUTTON_WORDS = frozenset(
    {
        "ok",
        "cancel",
        "save",
        "submit",
        "close",
        "apply",
        "delete",
        "settings",
        "login",
        "sign in",
        "continue",
        "next",
        "back",
        "refresh",
        "search",
        "file",
        "edit",
        "view",
        "help",
    }
)
_ERROR_WORDS = re.compile(
    r"\b(error|failed|warning|exception|denied|refused|traceback)\b",
    re.I,
)
_STATUS_WORDS = re.compile(
    r"\b(status|dashboard|connected|running|idle|healthy|offline|online)\b",
    re.I,
)


def _screen_enabled() -> bool:
    return bool(config.SCREEN_UNDERSTANDING_ENABLED)


def _pipeline(
    *,
    mode: str | None = None,
    window_meta: ActiveWindowMeta | None = None,
) -> tuple[ActiveWindowMeta, CaptureResult, ScreenOcrResult]:
    meta = window_meta or get_active_window_metadata()
    capture = safe_capture_screen(mode=mode, window_meta=meta)
    ocr = ScreenOcrResult(ok=False, engine="skipped", warning="No capture.")
    if capture.ok and capture.image is not None and not meta.is_blocked:
        ensure_ocr_temp_path(capture)
        ocr = run_screen_ocr(capture.image)
        delete_capture_temp(capture)
    elif meta.is_blocked:
        ocr = ScreenOcrResult(
            ok=False,
            engine="blocked",
            warning=meta.block_reason or "Secret-sensitive window blocked.",
        )
    elif capture.error:
        ocr = ScreenOcrResult(ok=False, engine="none", warning=capture.error)
    return meta, capture, ocr


def _infer_app(title: str, sample: str) -> str:
    combined = f"{title} {sample}".lower()
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
        ("settings", "Settings"),
    ]
    for key, label in hints:
        if key in combined:
            return label
    if title.strip():
        return f"Window: {title[:80]}"
    return "Unknown application"


def _detect_ui_elements(lines: list[str]) -> list[str]:
    found: list[str] = []
    for line in lines[:80]:
        low = line.lower().strip()
        if not low:
            continue
        for word in _BUTTON_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", low):
                found.append(f"button:{word}")
                break
        if _ERROR_WORDS.search(line):
            found.append("pattern:error_or_warning")
        if _STATUS_WORDS.search(line):
            found.append("pattern:status_or_dashboard")
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:20]


def summarize_screen(
    ocr_text: str,
    metadata: dict[str, Any],
    *,
    ocr_ok: bool = True,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Deterministic summary from redacted OCR + metadata."""
    title = metadata.get("active_window_title", "") or metadata.get("title", "")
    process = metadata.get("active_process", "") or metadata.get("process_name", "")
    lines = [ln.strip() for ln in (ocr_text or "").splitlines() if ln.strip()]
    preview = lines[:10]
    likely = _infer_app(title, " ".join(preview[:5]))
    ui_elements = _detect_ui_elements(lines)

    status = "ok"
    if metadata.get("is_blocked"):
        status = "blocked"
    elif not ocr_ok and not preview:
        status = "degraded"

    visible_summary = (
        "; ".join(preview[:6]) if preview else "(little or no visible text detected)"
    )
    if len(visible_summary) > 500:
        visible_summary = visible_summary[:497] + "..."

    safety_notes = [
        "Read-only screen understanding — no mouse, keyboard, or clicks.",
        "Screenshots are temporary unless SCREEN_CAPTURE_SAVE_DEBUG=true.",
    ]
    if metadata.get("is_blocked"):
        safety_notes.append("Capture/OCR skipped for secret-sensitive window.")

    return {
        "status": status,
        "active_window": {"title": title, "process": process, **metadata},
        "visible_text_summary": visible_summary,
        "likely_app_or_page": likely,
        "detected_ui_elements": ui_elements,
        "warnings": list(warnings or []) + ([metadata.get("warning")] if metadata.get("warning") else []),
        "safety_notes": safety_notes,
    }


def _format_summary_block(summary: dict[str, Any]) -> str:
    parts = [
        f"Status: {summary.get('status', 'unknown')}",
        f"Active window: {summary['active_window'].get('title') or '(unknown)'}",
        f"Likely app: {summary.get('likely_app_or_page', 'unknown')}",
        f"Visible text: {summary.get('visible_text_summary', '')}",
    ]
    ui = summary.get("detected_ui_elements") or []
    if ui:
        parts.append("UI hints: " + ", ".join(ui[:8]))
    warns = [w for w in (summary.get("warnings") or []) if w]
    if warns:
        parts.append("Warnings: " + "; ".join(str(w) for w in warns[:3]))
    return "\n".join(parts)


def describe_screen_v35() -> dict[str, Any]:
    if not _screen_enabled():
        return {
            "summary": SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
            "disabled": True,
        }
    meta, capture, ocr = _pipeline(mode=SCREEN_CAPTURE_MODE)
    redacted = redact_screen_text(ocr.text, max_len=SCREEN_MAX_TEXT_CHARS)
    md = {
        "active_window_title": meta.title,
        "active_process": meta.process_name,
        "pid": meta.pid,
        "is_blocked": meta.is_blocked,
        "block_reason": meta.block_reason,
        "capture_mode": capture.mode,
        "capture_ok": capture.ok,
        "warning": capture.warning or meta.warning,
    }
    summary = summarize_screen(
        redacted,
        md,
        ocr_ok=ocr.ok,
        warnings=[ocr.warning, ocr.error] if ocr.error else ([ocr.warning] if ocr.warning else None),
    )
    text_block = _format_summary_block(summary)
    return {
        "summary": text_block,
        "screen_summary": summary,
        "capture": {
            "ok": capture.ok,
            "mode": capture.mode,
            "image_size": capture.image_size,
            "temp_path_used": capture.temp_path_used,
            "deleted_after_use": capture.deleted_after_use,
        },
        "ocr_engine": ocr.engine,
        "redaction_applied": True,
        "screen_summary_length": len(redacted),
    }


def read_screen_v35() -> dict[str, Any]:
    if not _screen_enabled():
        return {
            "summary": SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
            "text": "",
            "disabled": True,
        }
    meta, capture, ocr = _pipeline(mode=SCREEN_CAPTURE_MODE)
    if meta.is_blocked:
        return {
            "summary": f"Screen read blocked: {meta.block_reason}",
            "text": "",
            "blocked": True,
        }
    redacted = redact_screen_text(ocr.text, max_len=SCREEN_MAX_TEXT_CHARS)
    if not ocr.ok and not redacted:
        msg = ocr.error or ocr.warning or capture.error or "OCR unavailable."
        return {"summary": f"Could not read screen text: {msg}", "text": "", "ocr_ok": False}
    summary = f"Read screen ({len(redacted)} chars, redacted)."
    if ocr.warning:
        summary += f" Note: {ocr.warning}"
    return {
        "summary": summary,
        "text": redacted,
        "ocr_engine": ocr.engine,
        "redaction_applied": True,
        "active_window_title": meta.title,
        "capture_mode": capture.mode,
    }


def analyze_active_window_v35() -> dict[str, Any]:
    if not _screen_enabled():
        return {
            "summary": SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
            "disabled": True,
        }
    meta = get_active_window_metadata()
    if meta.is_blocked:
        return {
            "summary": f"Active window analysis blocked: {meta.block_reason}",
            "active_window": {
                "title": meta.title,
                "process_name": meta.process_name,
                "pid": meta.pid,
                "is_blocked": True,
                "block_reason": meta.block_reason,
            },
            "blocked": True,
        }
    _, capture, ocr = _pipeline(mode="active_window", window_meta=meta)
    redacted = redact_screen_text(ocr.text, max_len=SCREEN_MAX_TEXT_CHARS)
    md = {
        "title": meta.title,
        "process_name": meta.process_name,
        "pid": meta.pid,
        "is_blocked": meta.is_blocked,
        "active_window_title": meta.title,
        "active_process": meta.process_name,
        "capture_mode": capture.mode,
    }
    summary = summarize_screen(
        redacted,
        md,
        ocr_ok=ocr.ok,
        warnings=[meta.warning, capture.warning, ocr.warning],
    )
    lines = [
        f"Active window: {meta.title or '(unknown)'}",
        f"Process: {meta.process_name or 'unknown'} (pid={meta.pid or 'n/a'})",
        f"Capture: {capture.mode} {capture.image_size}",
        _format_summary_block(summary),
    ]
    return {
        "summary": "\n".join(lines),
        "active_window": md,
        "screen_summary": summary,
        "text_preview": redacted[:800] if redacted else "",
        "ocr_engine": ocr.engine,
        "redaction_applied": True,
        "screen_summary_length": len(redacted),
    }


def _region_label(block: OcrBlock, image_h: int) -> str:
    if image_h <= 0:
        return "section:unknown"
    cy = block.top + block.height // 2
    third = image_h // 3
    if cy < third:
        return "section:top"
    if cy < 2 * third:
        return "section:middle"
    return "section:bottom"


def find_on_screen_v35(query: str) -> dict[str, Any]:
    if not _screen_enabled():
        return {
            "summary": SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
            "matches": [],
            "disabled": True,
        }
    q = (query or "").strip()
    if not q:
        return {
            "summary": "find on screen requires a search phrase.",
            "matches": [],
            "no_click": True,
        }
    meta, capture, ocr = _pipeline(mode=SCREEN_CAPTURE_MODE)
    if meta.is_blocked:
        return {
            "summary": f"Search blocked: {meta.block_reason}",
            "matches": [],
            "no_click": True,
        }
    redacted = redact_screen_text(ocr.text, max_len=SCREEN_MAX_TEXT_CHARS)
    matches: list[dict[str, Any]] = []
    q_low = q.lower()
    image_h = capture.image_size[1] if capture.image_size else 0

    # Block-level matches
    for block in ocr.blocks:
        if q_low not in block.text.lower():
            continue
        region = {
            "top_left": (block.left, block.top),
            "center": (
                block.left + block.width // 2,
                block.top + block.height // 2,
            ),
            "section": _region_label(block, image_h),
        }
        matches.append(
            {
                "match": redact_screen_text(block.text),
                "context": redact_screen_text(block.text),
                "region": region,
            }
        )
        if len(matches) >= SCREEN_FIND_MAX_RESULTS:
            break

    # Line context matches
    if len(matches) < SCREEN_FIND_MAX_RESULTS:
        for line in redacted.splitlines():
            if q_low not in line.lower():
                continue
            if any(m.get("context") == line for m in matches):
                continue
            matches.append(
                {
                    "match": line.strip()[:200],
                    "context": line.strip()[:300],
                    "region": None,
                }
            )
            if len(matches) >= SCREEN_FIND_MAX_RESULTS:
                break

    if matches:
        summary = f"Found {len(matches)} match(es) for '{q}' on screen."
    else:
        summary = f"No matches for '{q}' on screen (OCR may be partial)."
    summary += " No click was performed."
    return {
        "summary": summary,
        "query": q,
        "matches": matches,
        "match_count": len(matches),
        "no_click": True,
        "no_click_message": "No click was performed.",
        "ocr_engine": ocr.engine,
        "redaction_applied": True,
    }


def extract_find_query(raw_text: str, params: dict[str, Any] | None = None) -> str:
    if params and params.get("query"):
        return str(params["query"]).strip()
    text = (raw_text or "").strip()
    patterns = [
        r"find\s+on\s+screen\s+(.+)$",
        r"find\s+this\s+on\s+screen\s+(.+)$",
        r"where\s+is\s+(.+?)\s+on\s+(?:the\s+)?screen",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return m.group(1).strip()
    return ""
