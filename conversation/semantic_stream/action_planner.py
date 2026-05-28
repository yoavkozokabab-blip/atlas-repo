"""Action planning before speech ends — classify only, never execute."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import CONFIDENCE_THRESHOLD, IMPLEMENTED_INTENTS
from conversation.semantic_stream.multi_intent import MultiIntentPlan, decompose_utterance


@dataclass(frozen=True)
class PlannedAction:
    intent: str
    canonical_text: str
    confidence: float
    segment_index: int = 0
    ready: bool = False


@dataclass
class ActionPlan:
    actions: list[PlannedAction] = field(default_factory=list)
    primary_intent: str = ""
    primary_confidence: float = 0.0
    plan_ready: bool = False

    def top(self) -> PlannedAction | None:
        return self.actions[0] if self.actions else None


def build_action_plan(text: str, *, session_context: object | None = None) -> ActionPlan:
    """
    Prefetch intents for each decomposed segment using rules/grammar/semantic only.
    """
    plan = ActionPlan()
    multi: MultiIntentPlan = decompose_utterance(text)
    try:
        from language.hybrid_understanding import classify_hybrid

        for seg in multi.segments:
            req, _sem = classify_hybrid(seg.text, session_context)
            intent_val = req.intent.value
            if intent_val not in IMPLEMENTED_INTENTS:
                continue
            ready = req.confidence >= CONFIDENCE_THRESHOLD
            plan.actions.append(
                PlannedAction(
                    intent=intent_val,
                    canonical_text=req.raw_text or seg.text,
                    confidence=req.confidence,
                    segment_index=seg.index,
                    ready=ready,
                )
            )
    except Exception:
        return plan
    if plan.actions:
        top = plan.actions[0]
        plan.primary_intent = top.intent
        plan.primary_confidence = top.confidence
        plan.plan_ready = top.ready and all(a.ready for a in plan.actions[:2])
    return plan
