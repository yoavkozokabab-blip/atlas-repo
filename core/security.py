"""Security validation before action execution."""

from __future__ import annotations

from config import ALLOWED_INTENTS, IMPLEMENTED_INTENTS
from core.results import result_blocked, result_clarification, result_not_implemented
from core.types import CommandRequest, CommandResult, Intent


def validate_intent(request: CommandRequest) -> CommandResult | None:
    """
    Return a CommandResult if the request must be blocked or clarified;
    return None if validation passes (confirmation handled in router).
    """
    intent_value = request.intent.value

    if request.intent == Intent.UNKNOWN:
        return result_blocked(
            Intent.UNKNOWN,
            "Could not understand the command. Please rephrase.",
        )

    if request.intent == Intent.CLARIFY:
        msg = str(request.params.get("clarification") or "").strip()
        if not msg:
            msg = "Command is ambiguous. Please be more specific."
        alts = request.params.get("alternatives")
        suggestions = [str(a) for a in alts][:4] if isinstance(alts, list) else None
        return result_clarification(
            Intent.CLARIFY,
            msg,
            next_suggestions=suggestions,
        )

    if intent_value not in ALLOWED_INTENTS:
        return result_blocked(
            request.intent,
            f"Intent '{intent_value}' is not on the allowlist.",
        )

    if intent_value not in IMPLEMENTED_INTENTS:
        return result_not_implemented(
            request.intent,
            f"Intent '{intent_value}' is allowed but not implemented yet.",
        )

    return None
