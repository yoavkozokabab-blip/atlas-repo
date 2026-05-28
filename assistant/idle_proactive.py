"""Idle proactive conversational intelligence (Phase 59)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from config import DATA_DIR
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.idle_proactive")

_IDLE_PATH = DATA_DIR / "idle_proactive.json"
_lock = threading.Lock()
_worker: threading.Thread | None = None
_stop = threading.Event()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    data = load_json(_IDLE_PATH, default={"hints": [], "last_tick": ""})
    return data if isinstance(data, dict) else {"hints": [], "last_tick": ""}


def _save(data: dict) -> None:
    atomic_write_json(_IDLE_PATH, data)


def _idle_seconds() -> float:
    try:
        import config as cfg

        return float(getattr(cfg, "CONVERSATION_IDLE_PROACTIVE_SECONDS", 120.0))
    except Exception:
        return 120.0


def generate_idle_conversational_hints(*, force: bool = False) -> list[str]:
    hints: list[str] = []
    try:
        from assistant.conversation_state import _load as load_conv

        conv = load_conv()
        unresolved = (conv.get("unresolved_question") or "").strip()
        if unresolved:
            hints.append(f"You asked about: {unresolved[:100]}. Want me to dig in?")
        tone = conv.get("emotional_tone") or "neutral"
        if tone == "frustrated":
            hints.append("I noticed frustration earlier — want a quick status check or fix attempt?")
    except Exception:
        pass
    try:
        from assistant.proactive_assistant import generate_proactive_suggestions

        for item in generate_proactive_suggestions(force=force)[:2]:
            msg = (item.get("message") or item.get("summary") or "").strip()
            if msg:
                hints.append(msg[:180])
    except Exception:
        pass
    if not hints and force:
        hints.append("I'm here if you want a quick summary or next action.")
    return hints[:4]


def show_idle_proactive_status() -> str:
    data = _load()
    hints = data.get("hints") or []
    lines = [
        "Idle proactive intelligence (Phase 59):",
        f"  last tick: {data.get('last_tick') or 'never'}",
        f"  stored hints: {len(hints)}",
    ]
    for hint in hints[:3]:
        lines.append(f"  - {str(hint)[:120]}")
    return "\n".join(lines)


def show_idle_proactive_hints() -> str:
    hints = generate_idle_conversational_hints(force=True)
    if not hints:
        return "No idle proactive hints right now."
    _save({"hints": hints, "last_tick": _now()})
    lines = ["Idle proactive hints:", *[f"  - {h}" for h in hints]]
    return "\n".join(lines)


def idle_proactive_tick() -> None:
    if not _enabled():
        return
    hints = generate_idle_conversational_hints()
    if not hints:
        return
    _save({"hints": hints, "last_tick": _now()})
    try:
        from ui.overlay_app import notify_overlay_conversation_stream

        notify_overlay_conversation_stream(partial=hints[0][:120], intent="idle_proactive")
    except Exception:
        pass
    logger.debug("Idle proactive hint: %s", hints[0][:80])


def _enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "CONVERSATION_IDLE_PROACTIVE_ENABLED", True))
    except Exception:
        return True


def _loop(interval: float) -> None:
    while not _stop.wait(timeout=interval):
        try:
            idle_proactive_tick()
        except Exception as exc:
            logger.debug("Idle proactive tick failed: %s", exc)


def start_idle_proactive_intelligence(*, interval_seconds: float | None = None) -> None:
    global _worker
    interval = interval_seconds or _idle_seconds()
    with _lock:
        if _worker and _worker.is_alive():
            return
        _stop.clear()
        _worker = threading.Thread(
            target=_loop,
            args=(max(30.0, interval),),
            name="jarvis-idle-proactive",
            daemon=True,
        )
        _worker.start()
    logger.info("Idle proactive intelligence started interval=%.0fs", interval)


def stop_idle_proactive_intelligence() -> None:
    _stop.set()


def reset_idle_proactive_for_tests() -> None:
    global _worker
    stop_idle_proactive_intelligence()
    with _lock:
        _worker = None
    _save({"hints": [], "last_tick": ""})
