"""Dynamic command reformulation from conversation graph context."""

from __future__ import annotations

import config as cfg
from conversation.semantic_stream.conversation_graph import get_conversation_graph


def reformulate_with_context(text: str) -> tuple[str, str]:
    """
  Carry over context: resolve pronouns / follow-ups using graph + classify context.
  Returns (reformulated_text, reason).
  """
    raw = (text or "").strip()
    if not cfg.CONV_REFORMULATION_ENABLED or not cfg.CONV_CONTEXT_CARRY_ENABLED:
        return raw, ""
    lower = raw.lower()
    if not lower:
        return raw, ""
    g = get_conversation_graph()
    last_intent = ""
    intents = g.recent_intents(limit=1)
    if intents:
        last_intent = intents[-1].intent
    elif g.last_intent_id:
        for node in g.nodes:
            if node.node_id == g.last_intent_id:
                last_intent = node.intent
                break
    if not last_intent:
        try:
            from conversation.context_store import get_classify_context

            ctx = get_classify_context()
            if ctx.get("last_intent"):
                last_intent = str(ctx["last_intent"])
        except Exception:
            pass
    if lower in {"open it", "open that", "show it", "show that", "do that again"}:
        if "report" in last_intent:
            return "show latest live report", "context_last_report"
        if "dashboard" in last_intent:
            return "open dashboard", "context_last_dashboard"
        if "test" in last_intent or "failing" in last_intent:
            return "show failing tests", "context_last_tests"
    if lower in {"what about that", "and that", "same thing"} and last_intent:
        token = last_intent.replace("_", " ")
        return f"show {token}", "context_repeat_intent"
    return raw, ""
