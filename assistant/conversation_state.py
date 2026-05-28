"""Real-time conversational state engine (Phase 56)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import DATA_DIR
from core.logger import setup_logger
from core.persistent_json import atomic_write_json, load_json

logger = setup_logger("jarvis.assistant.conversation_state")

CONVERSATION_STATE_PATH = DATA_DIR / "conversation_state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "current_topic": "",
        "previous_topics": [],
        "active_project": "",
        "unresolved_question": "",
        "emotional_tone": "neutral",
        "interruption_state": "idle",
        "pending_actions": [],
        "recent_entities": [],
        "follow_up_references": [],
        "turn_count": 0,
        "last_user_text": "",
        "last_assistant_summary": "",
        "last_intent": "",
        "paused_response": "",
        "continuous_listening": False,
        "updated_at": "",
    }


def _load() -> dict[str, Any]:
    def _validate(data: Any) -> dict[str, Any] | None:
        return data if isinstance(data, dict) else None

    state = load_json(CONVERSATION_STATE_PATH, default=_default_state(), validator=_validate)
    base = _default_state()
    base.update(state)
    return base


def _save(data: dict[str, Any]) -> None:
    data["updated_at"] = _now()
    atomic_write_json(CONVERSATION_STATE_PATH, data)


def _push_unique(items: list[str], value: str, *, limit: int = 12) -> list[str]:
    value = (value or "").strip()
    if not value:
        return items
    return [value] + [x for x in items if x != value][: limit - 1]


def reset_conversation_state_for_tests() -> None:
    _save(_default_state())


def record_turn(
    *,
    raw_text: str,
    intent: str,
    summary: str,
    status: str = "success",
    input_mode: str = "text",
) -> None:
    """Persist conversational turn metadata after router completion."""
    data = _load()
    text = (raw_text or "").strip()
    data["turn_count"] = int(data.get("turn_count") or 0) + 1
    data["last_user_text"] = text[:400]
    data["last_assistant_summary"] = (summary or "")[:600]
    data["last_intent"] = (intent or "")[:80]
    if text:
        topic = text[:120]
        if topic != data.get("current_topic"):
            prev = (data.get("current_topic") or "").strip()
            if prev:
                data["previous_topics"] = _push_unique(list(data.get("previous_topics") or []), prev)
            data["current_topic"] = topic
    if "?" in text:
        data["unresolved_question"] = text[:240]
    elif status == "success" and data.get("unresolved_question"):
        data["unresolved_question"] = ""
    for token in _extract_entities(text):
        data["recent_entities"] = _push_unique(list(data.get("recent_entities") or []), token, limit=16)
    tone = _infer_tone(text)
    if tone:
        data["emotional_tone"] = tone
    if input_mode == "voice":
        data["follow_up_references"] = _push_unique(
            list(data.get("follow_up_references") or []),
            f"voice:{intent}",
            limit=8,
        )
    _save(data)


def _extract_entities(text: str) -> list[str]:
    words = [w.strip(".,!?\"'") for w in text.split() if len(w.strip(".,!?\"'")) >= 4]
    return words[:3]


def _infer_tone(text: str) -> str:
    lower = (text or "").lower()
    if any(x in lower for x in ("thanks", "great", "perfect", "awesome")):
        return "positive"
    if any(x in lower for x in ("stuck", "broken", "fail", "error", "why won't", "frustrated")):
        return "frustrated"
    if any(x in lower for x in ("confused", "don't understand", "what is", "explain")):
        return "curious"
    return "neutral"


def set_interruption_state(state: str) -> None:
    data = _load()
    data["interruption_state"] = (state or "idle")[:40]
    _save(data)


def store_paused_response(text: str) -> None:
    data = _load()
    data["paused_response"] = (text or "")[:1200]
    data["interruption_state"] = "paused_response"
    _save(data)


def clear_paused_response() -> str:
    data = _load()
    paused = (data.get("paused_response") or "").strip()
    data["paused_response"] = ""
    data["interruption_state"] = "idle"
    _save(data)
    return paused


def set_continuous_listening(active: bool) -> None:
    data = _load()
    data["continuous_listening"] = bool(active)
    _save(data)


def is_continuous_listening() -> bool:
    return bool(_load().get("continuous_listening"))


def what_are_we_discussing() -> str:
    data = _load()
    topic = data.get("current_topic") or "(no active topic yet)"
    unresolved = data.get("unresolved_question") or ""
    lines = [
        "Current conversation topic:",
        f"  {topic}",
        f"  turns: {data.get('turn_count', 0)}",
        f"  tone: {data.get('emotional_tone', 'neutral')}",
        f"  interruption: {data.get('interruption_state', 'idle')}",
    ]
    if unresolved:
        lines.append(f"  unresolved question: {unresolved[:160]}")
    if data.get("recent_entities"):
        lines.append(f"  recent entities: {', '.join(data['recent_entities'][:6])}")
    return "\n".join(lines)


def summarize_current_conversation() -> str:
    data = _load()
    lines = [
        "Conversation summary:",
        f"  topic: {data.get('current_topic') or 'n/a'}",
        f"  last intent: {data.get('last_intent') or 'n/a'}",
        f"  last user: {(data.get('last_user_text') or 'n/a')[:120]}",
        f"  last response: {(data.get('last_assistant_summary') or 'n/a')[:180]}",
        f"  pending actions: {len(data.get('pending_actions') or [])}",
        f"  continuous listening: {'yes' if data.get('continuous_listening') else 'no'}",
    ]
    prev = data.get("previous_topics") or []
    if prev:
        lines.append(f"  previous topics: {', '.join(prev[:4])}")
    return "\n".join(lines)


def resume_previous_topic() -> str:
    data = _load()
    prev = list(data.get("previous_topics") or [])
    if not prev:
        paused = (data.get("paused_response") or "").strip()
        if paused:
            return f"Resuming interrupted response:\n{paused[:800]}"
        return "No previous topic to resume."
    topic = prev.pop(0)
    data["previous_topics"] = prev
    data["current_topic"] = topic
    paused = (data.get("paused_response") or "").strip()
    _save(data)
    body = f"Resumed topic: {topic}"
    if paused:
        body += f"\nInterrupted response preserved:\n{paused[:600]}"
    return body


def show_conversation_state() -> str:
    data = _load()
    lines = [
        "Conversation state (Phase 56):",
        f"  current topic: {data.get('current_topic') or 'n/a'}",
        f"  active project: {data.get('active_project') or 'n/a'}",
        f"  emotional tone: {data.get('emotional_tone', 'neutral')}",
        f"  interruption state: {data.get('interruption_state', 'idle')}",
        f"  continuous listening: {'yes' if data.get('continuous_listening') else 'no'}",
        f"  turn count: {data.get('turn_count', 0)}",
        f"  unresolved question: {data.get('unresolved_question') or 'n/a'}",
        f"  pending actions: {len(data.get('pending_actions') or [])}",
        f"  recent entities: {', '.join((data.get('recent_entities') or [])[:8]) or 'n/a'}",
        f"  paused response chars: {len(data.get('paused_response') or '')}",
    ]
    return "\n".join(lines)


def get_overlay_snapshot() -> dict[str, Any]:
    data = _load()
    return {
        "conversation_topic": (data.get("current_topic") or "")[:60],
        "interruption_state": data.get("interruption_state", "idle"),
        "continuous_listening": bool(data.get("continuous_listening")),
        "unresolved_question": (data.get("unresolved_question") or "")[:60],
        "tone": data.get("emotional_tone", "neutral"),
        "turn_count": int(data.get("turn_count") or 0),
    }
