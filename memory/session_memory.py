"""Phase 40e — rolling session memory (local, redacted)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DATA_DIR, SESSION_MEMORY_ENABLED, SESSION_MEMORY_PATH
from core.logger import setup_logger
from core.session import SessionState
from operating.workspace_context import get_cached_mode
from vision.redaction import redact_sensitive_text

logger = setup_logger("jarvis.memory.session")

_MAX_EVENTS = 200
_SUMMARY_EVENTS = 80


@dataclass
class SessionEvent:
    intent: str
    status: str
    summary: str
    timestamp: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_raw() -> dict[str, Any]:
    path = Path(SESSION_MEMORY_PATH)
    if not path.is_file():
        return {"events": [], "summaries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("events", [])
            data.setdefault("summaries", [])
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"events": [], "summaries": []}


def _save_raw(data: dict[str, Any]) -> None:
    path = Path(SESSION_MEMORY_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("session_memory save failed: %s", exc)


def append_session_event(intent: str, status: str, summary_excerpt: str) -> None:
    if not SESSION_MEMORY_ENABLED:
        return
    try:
        data = _load_raw()
        events: list[dict[str, Any]] = list(data.get("events") or [])
        events.append(
            {
                "intent": intent,
                "status": status,
                "summary": redact_sensitive_text(summary_excerpt[:300]),
                "timestamp": _now(),
            }
        )
        if len(events) > _MAX_EVENTS:
            events = events[-_MAX_EVENTS:]
        data["events"] = events
        _save_raw(data)
    except Exception as exc:
        logger.debug("append_session_event: %s", exc)


def get_recent_intents(*, limit: int = 5) -> list[str]:
    """Recent command intents for STT context repair."""
    data = _load_raw()
    events = data.get("events") or []
    intents: list[str] = []
    for e in reversed(events):
        intent = str(e.get("intent", "")).strip()
        if intent and intent not in intents:
            intents.append(intent)
        if len(intents) >= limit:
            break
    return intents


def summarize_session() -> str:
    data = _load_raw()
    events = data.get("events") or []
    if not events:
        return "No session events recorded yet."
    recent = events[-_SUMMARY_EVENTS:]
    intents = Counter(str(e.get("intent", "")) for e in recent)
    errors = [e for e in recent if str(e.get("status", "")) in ("failed", "blocked")]
    session = SessionState.load()
    mode = get_cached_mode() or session.activity_mode or "idle"
    lines = [
        "Session summary (deterministic)",
        f"  Workspace mode: {mode}",
        f"  Project: {Path(session.current_project_root or '.').name}",
        f"  Commands in buffer: {len(recent)}",
        "  Top intents:",
    ]
    for intent, count in intents.most_common(5):
        if intent:
            lines.append(f"    - {intent}: {count}")
    if errors:
        lines.append(f"  Recent errors: {len(errors)}")
        for e in errors[-3:]:
            lines.append(f"    - {e.get('intent')}: {str(e.get('summary', ''))[:80]}")
    else:
        lines.append("  Recent errors: none")
    lines.append("  Continue with: what were we doing")
    return "\n".join(lines)


def persist_session_summary() -> None:
    if not SESSION_MEMORY_ENABLED:
        return
    try:
        summary = summarize_session()
        data = _load_raw()
        summaries: list[dict[str, Any]] = list(data.get("summaries") or [])
        summaries.append({"text": summary, "timestamp": _now()})
        if len(summaries) > 20:
            summaries = summaries[-20:]
        data["summaries"] = summaries
        _save_raw(data)
    except Exception as exc:
        logger.debug("persist_session_summary: %s", exc)


def restore_context() -> str:
    data = _load_raw()
    events = data.get("events") or []
    summaries = data.get("summaries") or []
    session = SessionState.load()
    lines = [
        "What we were doing",
        f"  Project: {Path(session.current_project_root or '.').name}",
        f"  Last intent: {session.last_intent or 'n/a'}",
        f"  Last result: {(session.last_result_summary or 'n/a')[:120]}",
        f"  Activity mode: {session.activity_mode or get_cached_mode() or 'idle'}",
    ]
    if summaries:
        last_sum = summaries[-1]
        lines.append(f"  Last session summary:\n{str(last_sum.get('text', ''))[:400]}")
    if events:
        lines.append("  Recent commands:")
        for e in events[-6:]:
            lines.append(
                f"    - {e.get('intent')} [{e.get('status')}]: "
                f"{str(e.get('summary', ''))[:60]}"
            )
    lines.append("  Suggested: summarize session, run diagnostics, what am i doing")
    return "\n".join(lines)


def reset_session_memory_file() -> None:
    path = Path(SESSION_MEMORY_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
