"""Phase 32 — command audit trail (JSONL, redacted, non-fatal)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR
from core.rotating_jsonl import RotatingJSONLWriter
from core.types import CommandRequest, CommandResult

COMMAND_AUDIT_PATH = DATA_DIR / "command_audit.jsonl"

# Lazy writer cache (VF-2 fix): keyed by resolved path string so that
# monkeypatch works correctly in tests.
_audit_writers: dict[str, RotatingJSONLWriter] = {}


def _get_audit_writer() -> RotatingJSONLWriter:
    path_str = str(COMMAND_AUDIT_PATH)
    if path_str not in _audit_writers:
        _audit_writers[path_str] = RotatingJSONLWriter(
            Path(COMMAND_AUDIT_PATH), max_bytes=5_000_000, backup_count=3
        )
    return _audit_writers[path_str]
DEFAULT_AUDIT_LIMIT = 20
MAX_SUMMARY_LEN = 400
MAX_RAW_TEXT_LEN = 200
MAX_PARAM_VALUE_LEN = 120
MAX_ERROR_LEN = 200

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*\S+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

_BLOCKED_PARAM_KEYS: frozenset[str] = frozenset(
    {
        "unified_diff",
        "patch",
        "diff",
        "file_content",
        "contents",
        "body",
        "env",
        "password",
        "token",
        "secret",
        "api_key",
    }
)

_SCREEN_AUDIT_INTENTS: frozenset[str] = frozenset(
    {
        "describe_screen",
        "read_screen_text",
        "analyze_active_window",
        "find_on_screen",
    }
)

_BLOCKED_SUBSTRINGS: tuple[str, ...] = (
    "unified diff",
    "+++ b/",
    "--- a/",
    "BEGIN PATCH",
    "OPENAI_API",
    "TELEGRAM_BOT",
)


def redact_text(text: str | None, *, max_len: int = MAX_SUMMARY_LEN) -> str:
    if not text:
        return ""
    out = str(text)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    out = re.sub(
        r"(?i)(OPENAI|TELEGRAM|API)[_A-Z]*\s*=\s*\S+",
        r"\1=***REDACTED***",
        out,
    )
    lower = out.lower()
    for marker in _BLOCKED_SUBSTRINGS:
        if marker.lower() in lower:
            return "[content omitted — patch/env/file body not logged]"
    if len(out) > max_len:
        out = out[:max_len] + "…"
    return out


def _sanitize_params(params: dict[str, Any] | None) -> dict[str, str]:
    if not params:
        return {}
    safe: dict[str, str] = {}
    for key, value in params.items():
        k = str(key).lower()
        if k in _BLOCKED_PARAM_KEYS or any(b in k for b in ("secret", "password", "token", "patch", "diff")):
            safe[str(key)] = "[omitted]"
            continue
        if isinstance(value, (dict, list)):
            safe[str(key)] = "[omitted — complex value]"
            continue
        safe[str(key)] = redact_text(str(value), max_len=MAX_PARAM_VALUE_LEN)
    return safe


def _screen_audit_fields(
    request: CommandRequest,
    result: CommandResult,
) -> dict[str, Any]:
    """Safe screen-command audit fields — never log OCR body."""
    data = result.data or {}
    title = ""
    aw = data.get("active_window")
    if isinstance(aw, dict):
        title = str(aw.get("title") or aw.get("active_window_title") or "")
    elif data.get("active_window_title"):
        title = str(data["active_window_title"])
    capture = data.get("capture") if isinstance(data.get("capture"), dict) else {}
    mode = data.get("capture_mode") or capture.get("mode") or ""
    length = data.get("screen_summary_length")
    if length is None and data.get("text"):
        length = len(str(data.get("text", "")))
    if length is None and data.get("screen_summary"):
        length = len(str(data.get("screen_summary")))
    return {
        "screen_summary_length": int(length) if length is not None else 0,
        "redaction_applied": bool(data.get("redaction_applied", True)),
        "active_window_title_redacted": redact_text(title, max_len=80),
        "mode": str(mode)[:40],
    }


def build_audit_entry(
    request: CommandRequest,
    result: CommandResult,
    duration_ms: int,
    *,
    log_meta: dict | None = None,
) -> dict[str, Any]:
    """Build a safe audit record (no secrets, no patch bodies)."""
    meta = log_meta or {}
    intent_val = request.intent.value
    is_screen = intent_val in _SCREEN_AUDIT_INTENTS

    summary = result.summary
    if is_screen:
        summary = redact_text(summary, max_len=200)
        if len(result.summary or "") > 200:
            summary = (summary[:180] + "… [screen summary truncated]") if summary else "[screen result omitted]"

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intent": intent_val,
        "status": result.status.value,
        "confidence": round(float(request.confidence), 3),
        "duration_ms": int(duration_ms),
        "input_mode": meta.get("input_mode", "text"),
        "classifier_source": getattr(request, "classifier_source", "rules"),
        "requires_confirmation": bool(result.requires_confirmation),
        "raw_text": redact_text(request.raw_text, max_len=MAX_RAW_TEXT_LEN),
        "summary": redact_text(summary, max_len=MAX_SUMMARY_LEN if not is_screen else 200),
        "params": _sanitize_params(request.params),
    }
    if is_screen:
        entry.update(_screen_audit_fields(request, result))
    data = result.data or {}
    if data.get("conversation_enhanced"):
        entry["conversation_enhanced"] = True
        entry["continuation_offered"] = bool(data.get("continuation_offered"))
        entry["suggestion_count"] = len(result.next_suggestions or [])
    if result.error:
        entry["error"] = redact_text(result.error, max_len=MAX_ERROR_LEN)
    transcribed = meta.get("transcribed_text")
    if transcribed:
        entry["transcribed_text"] = redact_text(str(transcribed), max_len=MAX_RAW_TEXT_LEN)
    return entry


def append_audit_event(
    request: CommandRequest,
    result: CommandResult,
    duration_ms: int,
    *,
    log_meta: dict | None = None,
) -> bool:
    """Append one audit line. Returns False on failure; never raises."""
    try:
        entry = build_audit_entry(request, result, duration_ms, log_meta=log_meta)
        _get_audit_writer().write_line(json.dumps(entry, ensure_ascii=False))
        return True
    except Exception:
        return False


def read_last_audit_entries(limit: int = DEFAULT_AUDIT_LIMIT) -> list[dict[str, Any]]:
    """Read last N audit entries (newest last)."""
    path = Path(COMMAND_AUDIT_PATH)
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines[-max(1, limit) :]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def format_audit_report(entries: list[dict[str, Any]], *, limit: int = DEFAULT_AUDIT_LIMIT) -> str:
    """Format audit entries for display (read-only)."""
    if not entries:
        return (
            f"Command audit trail (last {limit})\n"
            "No audit entries yet.\n"
            f"Log file: {COMMAND_AUDIT_PATH}"
        )
    lines = [
        f"Command audit trail (last {len(entries)} of max {limit})",
        f"Source: {COMMAND_AUDIT_PATH}",
        "",
    ]
    for i, ent in enumerate(entries, start=1):
        lines.append(
            f"{i}. [{ent.get('timestamp', '?')}] "
            f"{ent.get('intent', '?')} → {ent.get('status', '?')} "
            f"({ent.get('duration_ms', 0)} ms)"
        )
        raw = ent.get("raw_text", "")
        if raw:
            lines.append(f"   text: {raw}")
        summary = ent.get("summary", "")
        if summary:
            lines.append(f"   summary: {summary}")
        if ent.get("requires_confirmation"):
            lines.append("   requires_confirmation: true")
        if ent.get("error"):
            lines.append(f"   error: {ent.get('error')}")
    lines.append("")
    lines.append("_Audit is redacted — no .env values, patch bodies, or file contents._")
    return "\n".join(lines)


def reset_audit_store() -> None:
    """Test helper — remove audit file and clear the writer cache."""
    # Clear the writer cache so the next call to _get_audit_writer() picks up
    # the (potentially monkeypatched) COMMAND_AUDIT_PATH.
    _audit_writers.clear()
    path = Path(COMMAND_AUDIT_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            try:
                path.write_text("", encoding="utf-8")
            except OSError:
                pass
