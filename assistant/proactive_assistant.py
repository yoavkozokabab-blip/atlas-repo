"""Conversational proactive assistance — rate-limited, non-spammy (Phase 56)."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.proactive_assistant")

PROACTIVE_PATH = DATA_DIR / "proactive_assistant.json"
_MIN_INTERVAL_S = 900.0
_MAX_SUGGESTIONS = 3

_thread: threading.Thread | None = None
_stop = threading.Event()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "last_suggestion_at": "",
        "last_suggestions": [],
        "dismissed": [],
        "updated_at": "",
    }


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(PROACTIVE_PATH, default=_default_state(), validator=_validate)
    base = _default_state()
    base.update(state)
    return base


def _save(data: dict[str, Any]) -> None:
    data["updated_at"] = _now()
    atomic_write_json(PROACTIVE_PATH, data)


def reset_proactive_assistant_for_tests() -> None:
    _save(_default_state())


def _rate_limited() -> bool:
    data = _load()
    last = data.get("last_suggestion_at") or ""
    if not last:
        return False
    try:
        prev = datetime.fromisoformat(last.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - prev).total_seconds()
        return elapsed < _MIN_INTERVAL_S
    except Exception:
        return False


def _collect_suggestions() -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []
    try:
        from assistant.conversation_state import _load as load_conv

        conv = load_conv()
        if conv.get("unresolved_question"):
            suggestions.append(
                {
                    "title": "Unresolved question",
                    "detail": conv["unresolved_question"][:120],
                    "action": "what are we discussing",
                }
            )
        if conv.get("emotional_tone") == "frustrated":
            suggestions.append(
                {
                    "title": "You seem stuck",
                    "detail": "Want me to summarize blockers or suggest next steps?",
                    "action": "recommend next action",
                }
            )
    except Exception:
        pass
    try:
        from assistant.root_cause_engine import get_overlay_snapshot

        rc = get_overlay_snapshot()
        if rc.get("dominant_root_cause"):
            suggestions.append(
                {
                    "title": "Verified root cause available",
                    "detail": str(rc["dominant_root_cause"])[:100],
                    "action": "summarize root causes",
                }
            )
    except Exception:
        pass
    try:
        from assistant.notifications import get_notification_store

        latest = get_notification_store().latest_unread()
        if latest:
            suggestions.append(
                {
                    "title": latest.title[:60],
                    "detail": latest.message[:120],
                    "action": "show notifications",
                }
            )
    except Exception:
        pass
    return suggestions[:_MAX_SUGGESTIONS]


def generate_proactive_suggestions(*, force: bool = False) -> list[dict[str, str]]:
    if not force and _rate_limited():
        return list(_load().get("last_suggestions") or [])
    suggestions = _collect_suggestions()
    data = _load()
    data["last_suggestions"] = suggestions
    if suggestions:
        data["last_suggestion_at"] = _now()
    _save(data)
    return suggestions


def show_proactive_suggestions() -> str:
    suggestions = generate_proactive_suggestions(force=True)
    if not suggestions:
        return "No proactive suggestions right now (nothing urgent detected)."
    lines = ["Proactive suggestions (not auto-applied):"]
    for idx, item in enumerate(suggestions, 1):
        lines.append(f"  [{idx}] {item.get('title', 'Suggestion')}")
        lines.append(f"      {item.get('detail', '')[:120]}")
        if item.get("action"):
            lines.append(f"      try: {item['action']}")
    return "\n".join(lines)


def proactive_tick() -> None:
    if os.environ.get("JARVIS_SKIP_PROACTIVE_ASSISTANT") == "1":
        return
    suggestions = generate_proactive_suggestions()
    if not suggestions:
        return
    try:
        from ui.overlay_app import notify_overlay_assistant_state

        notify_overlay_assistant_state()
    except Exception:
        pass
    logger.debug("Proactive assistant tick: %d suggestions", len(suggestions))


def start_proactive_assistant(*, interval_seconds: float = 300.0) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()

    def _loop() -> None:
        while not _stop.wait(max(60.0, interval_seconds)):
            try:
                proactive_tick()
            except Exception as exc:
                logger.debug("proactive assistant tick failed: %s", exc)

    _thread = threading.Thread(target=_loop, name="jarvis-proactive-assistant", daemon=True)
    _thread.start()
    logger.info("Proactive assistant started (interval=%.0fs)", interval_seconds)


def stop_proactive_assistant() -> None:
    _stop.set()


def get_overlay_snapshot() -> dict[str, Any]:
    data = _load()
    suggestions = data.get("last_suggestions") or []
    return {
        "proactive_count": len(suggestions),
        "latest_proactive": (suggestions[0].get("title") if suggestions else "")[:50],
    }
