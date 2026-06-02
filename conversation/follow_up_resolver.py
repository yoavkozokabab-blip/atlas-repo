"""Natural conversational follow-up resolution (Voice-Hardening)."""

from __future__ import annotations

import re
import unicodedata

_ORDINAL_WORDS = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "last": -1,
    "previous": -2,
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def _recent_user_texts(limit: int = 20) -> list[str]:
    try:
        from conversation.context_store import get_recent_turns

        return [
            t.raw_text_excerpt or t.summary_excerpt
            for t in get_recent_turns(limit=limit)
            if (t.raw_text_excerpt or t.summary_excerpt)
        ]
    except Exception:
        return []


def _last_assistant_summary() -> str:
    try:
        from conversation.memory_runtime import get_conversational_context

        return str(get_conversational_context().get("last_assistant_summary") or "")
    except Exception:
        return ""


def _last_intent() -> str:
    try:
        from conversation.context_store import get_classify_context

        ctx = get_classify_context()
        return str(ctx.get("last_intent") or "")
    except Exception:
        return ""


def resolve_follow_up_text(text: str) -> tuple[str, str]:
    """
    Expand deictic / continuation phrases using the last 20-turn window.

    Returns (resolved_text, reason_tag). Empty reason means no rewrite.
    """
    raw = (text or "").strip()
    norm = _normalize(raw)
    if not norm:
        return raw, ""

    from conversation.semantic_stream.reformulation import reformulate_with_context

    reformulated, ref_reason = reformulate_with_context(raw)
    if ref_reason:
        return reformulated, ref_reason

    if norm in {
        "tell me more",
        "say more",
        "go on",
        "continue",
        "more details",
        "explain more",
        "elaborate",
    }:
        topic = _last_assistant_summary() or _last_intent().replace("_", " ")
        if topic:
            return f"tell me more about {topic[:120]}", "continuation_tell_more"

    compare = re.match(
        r"compare\s+(?:it|that|this)\s+to\s+(.+)",
        norm,
    )
    if compare:
        subject = (_last_assistant_summary() or _last_intent().replace("_", " "))[:80]
        target = compare.group(1).strip()
        if subject and target:
            return f"compare {subject} to {target}", "continuation_compare"

    what_about = re.match(
        r"what about\s+(?:the\s+)?(first|second|third|fourth|last|previous)\s+one",
        norm,
    )
    if what_about:
        idx_key = what_about.group(1)
        idx = _ORDINAL_WORDS.get(idx_key, -1)
        users = _recent_user_texts(limit=20)
        if users:
            pick = users[idx] if abs(idx) < len(users) else users[-1]
            return pick, f"ordinal_{idx_key}"

    if norm in {"what about that", "and that", "how about that"}:
        pending = ""
        try:
            from conversation.memory_runtime import get_conversational_context

            pending = str(get_conversational_context().get("pending_follow_up") or "")
        except Exception:
            pass
        if pending:
            return pending, "pending_follow_up"

    return raw, ""

