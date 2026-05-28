"""Conversational memory runtime — topic continuity and turn references (Phase 59)."""

from __future__ import annotations

from typing import Any

from assistant.conversation_state import _load, _save, _push_unique
from core.logger import setup_logger

logger = setup_logger("jarvis.conversation.memory_runtime")


def _default_extensions() -> dict[str, Any]:
    return {
        "interruption_count": 0,
        "intent_continuity_chain": [],
        "turn_references": [],
        "last_response_style": "neutral",
        "pending_follow_up": "",
        "user_intent_continuity": "",
    }


def _ensure_extensions(data: dict[str, Any]) -> dict[str, Any]:
    for key, value in _default_extensions().items():
        data.setdefault(key, value if not isinstance(value, list) else list(value))
    return data


def load_memory_runtime() -> dict[str, Any]:
    data = _ensure_extensions(_load())
    return data


def record_conversational_turn(
    *,
    user_text: str,
    assistant_text: str,
    intent: str,
    status: str = "success",
    input_mode: str = "voice",
    speech_style: str = "neutral",
) -> None:
    from assistant.conversation_state import record_turn

    record_turn(
        raw_text=user_text,
        intent=intent,
        summary=assistant_text,
        status=status,
        input_mode=input_mode,
    )
    data = _ensure_extensions(_load())
    data["last_response_style"] = speech_style[:40]
    if intent:
        data["intent_continuity_chain"] = _push_unique(
            list(data.get("intent_continuity_chain") or []),
            intent,
            limit=10,
        )
        data["user_intent_continuity"] = intent[:80]
    ref = f"{(user_text or '')[:60]} -> {(assistant_text or '')[:80]}"
    data["turn_references"] = _push_unique(
        list(data.get("turn_references") or []),
        ref,
        limit=12,
    )
    if "?" in (user_text or ""):
        data["pending_follow_up"] = user_text[:240]
    elif status == "success":
        data["pending_follow_up"] = ""
    _save(data)


def record_interruption_event(*, partial_text: str = "") -> None:
    del partial_text
    data = _ensure_extensions(_load())
    data["interruption_count"] = int(data.get("interruption_count") or 0) + 1
    _save(data)


def get_conversational_context() -> dict[str, Any]:
    data = load_memory_runtime()
    return {
        "current_topic": data.get("current_topic") or "",
        "unresolved_question": data.get("unresolved_question") or "",
        "emotional_tone": data.get("emotional_tone") or "neutral",
        "last_user_text": data.get("last_user_text") or "",
        "last_assistant_summary": data.get("last_assistant_summary") or "",
        "last_intent": data.get("last_intent") or "",
        "intent_continuity": data.get("user_intent_continuity") or "",
        "turn_count": int(data.get("turn_count") or 0),
        "interruption_count": int(data.get("interruption_count") or 0),
        "turn_references": list(data.get("turn_references") or [])[:6],
        "pending_follow_up": data.get("pending_follow_up") or "",
    }


def build_llm_context_prompt() -> str:
    ctx = get_conversational_context()
    lines = [
        "Conversation context:",
        f"- topic: {ctx['current_topic'] or 'none'}",
        f"- tone: {ctx['emotional_tone']}",
        f"- last user: {ctx['last_user_text'][:120]}",
        f"- last assistant: {ctx['last_assistant_summary'][:160]}",
        f"- intent continuity: {ctx['intent_continuity'] or 'n/a'}",
    ]
    if ctx["unresolved_question"]:
        lines.append(f"- unresolved question: {ctx['unresolved_question'][:160]}")
    if ctx["pending_follow_up"]:
        lines.append(f"- pending follow-up: {ctx['pending_follow_up'][:160]}")
    refs = ctx.get("turn_references") or []
    if refs:
        lines.append("- recent turns:")
        lines.extend(f"  * {r[:140]}" for r in refs[:4])
    return "\n".join(lines)


def show_conversational_memory() -> str:
    ctx = get_conversational_context()
    data = load_memory_runtime()
    lines = [
        "Conversational memory (Phase 59):",
        f"  active topic: {ctx['current_topic'] or 'n/a'}",
        f"  unresolved question: {ctx['unresolved_question'] or 'n/a'}",
        f"  emotional tone: {ctx['emotional_tone']}",
        f"  interruptions: {ctx['interruption_count']}",
        f"  intent continuity: {ctx['intent_continuity'] or 'n/a'}",
        f"  pending follow-up: {ctx['pending_follow_up'] or 'n/a'}",
        f"  last response style: {data.get('last_response_style') or 'neutral'}",
        f"  turn count: {ctx['turn_count']}",
    ]
    refs = ctx.get("turn_references") or []
    if refs:
        lines.append("  recent references:")
        for ref in refs[:5]:
            lines.append(f"    - {ref[:120]}")
    chain = data.get("intent_continuity_chain") or []
    if chain:
        lines.append(f"  intent chain: {', '.join(chain[:6])}")
    return "\n".join(lines)


def reset_memory_runtime_for_tests() -> None:
    from assistant.conversation_state import reset_conversation_state_for_tests

    reset_conversation_state_for_tests()
    _save(_ensure_extensions(_default_state_patch()))


def _default_state_patch() -> dict[str, Any]:
    base = {
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
    base.update(_default_extensions())
    return base
