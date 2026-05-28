"""Intent prefetch during speech — classify only, never execute."""

from __future__ import annotations

from dataclasses import dataclass

from config import STT_INTENT_PREFETCH_ENABLED
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.streaming.prefetch")


@dataclass(frozen=True)
class PrefetchResult:
    intent: str
    confidence: float
    canonical_text: str
    ready: bool
    reason: str = ""


def prefetch_intent(
    partial_text: str,
    *,
    session_context: object | None = None,
    min_chars: int = 8,
) -> PrefetchResult | None:
    """
    Rules/grammar-only prefetch (fast). Router still required for execution.
    """
    if not STT_INTENT_PREFETCH_ENABLED:
        return None
    text = (partial_text or "").strip()
    if len(text) < min_chars:
        return None
    try:
        from brain.intent_classifier import classify_rules
        from config import CONFIDENCE_THRESHOLD
        from core.types import Intent

        req = classify_rules(text)
        if req.intent in (Intent.UNKNOWN, Intent.CLARIFY):
            return PrefetchResult(
                intent=req.intent.value,
                confidence=req.confidence,
                canonical_text=text,
                ready=False,
                reason="not_ready",
            )
        ready = req.confidence >= CONFIDENCE_THRESHOLD
        return PrefetchResult(
            intent=req.intent.value,
            confidence=req.confidence,
            canonical_text=req.raw_text or text,
            ready=ready,
            reason="rules_prefetch",
        )
    except Exception as exc:
        logger.debug("prefetch skipped: %s", exc)
        return None
