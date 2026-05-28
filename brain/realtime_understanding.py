"""Mid-sentence intent prediction and early preparation (Phase 56)."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.brain.realtime_understanding")


@dataclass(frozen=True)
class RealtimePrediction:
    partial_text: str
    intent: str
    confidence: float
    ready: bool
    candidates: tuple[str, ...] = ()
    early_ack: str = ""
    action_plan: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""


def predict_intent(
    partial_text: str,
    *,
    session_context: object | None = None,
    min_chars: int = 6,
) -> RealtimePrediction | None:
    """Predict intent mid-sentence; never executes commands."""
    text = (partial_text or "").strip()
    if len(text) < min_chars:
        return None
    try:
        from voice.streaming_stt.intent_prefetch import prefetch_intent

        prefetch = prefetch_intent(text, session_context=session_context, min_chars=min_chars)
        if prefetch is None:
            return _predict_from_context(text, session_context)
        candidates = _candidate_intents(text, prefetch.intent)
        plan = _build_action_plan(text, prefetch.intent) if prefetch.ready else ()
        ack = _early_ack_for_intent(prefetch.intent, text) if prefetch.ready else ""
        return RealtimePrediction(
            partial_text=text,
            intent=prefetch.intent,
            confidence=prefetch.confidence,
            ready=prefetch.ready,
            candidates=candidates,
            early_ack=ack,
            action_plan=plan,
            reason=prefetch.reason or "prefetch",
        )
    except Exception as exc:
        logger.debug("predict_intent skipped: %s", exc)
        return _predict_from_context(text, session_context)


def _predict_from_context(text: str, session_context: object | None) -> RealtimePrediction | None:
    try:
        from brain.intent_classifier import classify_rules
        from config import CONFIDENCE_THRESHOLD
        from core.types import Intent

        req = classify_rules(text)
        if req.intent in (Intent.UNKNOWN, Intent.CLARIFY):
            return None
        ready = req.confidence >= CONFIDENCE_THRESHOLD
        return RealtimePrediction(
            partial_text=text,
            intent=req.intent.value,
            confidence=req.confidence,
            ready=ready,
            candidates=_candidate_intents(text, req.intent.value),
            early_ack=_early_ack_for_intent(req.intent.value, text) if ready else "",
            action_plan=_build_action_plan(text, req.intent.value) if ready else (),
            reason="rules_fallback",
        )
    except Exception:
        return None


def _candidate_intents(text: str, primary: str) -> tuple[str, ...]:
    lower = (text or "").lower()
    candidates = [primary]
    if "open" in lower or "switch" in lower or "focus" in lower:
        candidates.extend(["switch_to_browser", "switch_to_cursor", "switch_to_dashboard"])
    if "project" in lower or "architecture" in lower:
        candidates.extend(["explain_this_project", "explain_architecture"])
    if "bug" in lower or "error" in lower or "fail" in lower:
        candidates.extend(["detect_screen_errors", "summarize_root_causes"])
    if "patch" in lower or "fix" in lower:
        candidates.extend(["propose_engineering_patch", "simulate_engineering_patch"])
    seen: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.append(item)
    return tuple(seen[:5])


def _build_action_plan(text: str, intent: str) -> tuple[str, ...]:
    try:
        from conversation.semantic_stream.action_planner import build_action_plan

        plan = build_action_plan(text)
        if plan.actions:
            return tuple(a.intent for a in plan.actions[:4] if a.intent)
    except Exception:
        pass
    return (intent,) if intent else ()


def _early_ack_for_intent(intent: str, text: str) -> str:
    lower = (text or "").lower()
    if intent.startswith("switch_") or "open" in lower:
        return "Opening that now."
    if "project" in lower or intent in {"explain_this_project", "explain_architecture"}:
        return "Reviewing the project context."
    if "error" in lower or intent == "detect_screen_errors":
        return "Checking what's on screen."
    if intent in {"what_are_we_discussing", "summarize_current_conversation"}:
        return "Pulling up our conversation context."
    return "One moment."


def prepare_speculative_response(partial_text: str, prediction: RealtimePrediction | None) -> dict[str, object]:
    """Prepare lightweight speculative context for low-latency replies."""
    if prediction is None or not prediction.ready:
        return {"ready": False}
    return {
        "ready": True,
        "intent": prediction.intent,
        "confidence": prediction.confidence,
        "candidates": list(prediction.candidates),
        "early_ack": prediction.early_ack,
        "partial": partial_text[:120],
    }
