"""Hybrid command understanding: rules → grammar → semantic → optional semantic LLM."""

from __future__ import annotations

import re
import unicodedata

import config as cfg
from config import CONFIDENCE_THRESHOLD, LLM_CLASSIFIER_ENABLED, LLM_FALLBACK_TO_RULES, SEMANTIC_MIN_CONFIDENCE
from core.types import CommandRequest, Intent
from language.semantic_context import SemanticContext, build_semantic_context
from language.semantic_intent import (
    SemanticUnderstanding,
    semantic_to_clarification_request,
    set_final_routed_intent,
    understand_semantic,
)
from language.vocabulary import correct_tokens

_last_hybrid_semantic: SemanticUnderstanding | None = None


def get_last_hybrid_semantic() -> SemanticUnderstanding | None:
    return _last_hybrid_semantic


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _record_semantic(sem: SemanticUnderstanding | None) -> None:
    global _last_hybrid_semantic
    _last_hybrid_semantic = sem
    try:
        from voice.voice_debug_store import record_semantic_debug

        if sem is not None:
            record_semantic_debug(sem)
    except Exception:
        pass


def _from_semantic_llm(
    text: str,
    *,
    normalized: str,
    ctx: SemanticContext,
) -> CommandRequest | None:
    from language.semantic_llm import plan_with_semantic_llm

    result = plan_with_semantic_llm(text, normalized=normalized, ctx=ctx)
    sem = SemanticUnderstanding(
        candidate_intent=result.intent if result.valid else "clarify",
        confidence=result.confidence,
        canonical_command=result.canonical_command,
        reasoning=result.reason,
        ambiguous=not result.valid,
        clarification=result.clarification or None,
        source="semantic_llm",
        llm_used=True,
        raw_transcript=text,
        normalized_transcript=normalized,
    )
    _record_semantic(sem)
    if not result.valid:
        msg, params = semantic_to_clarification_request(text, sem)
        return CommandRequest(
            raw_text=text,
            intent=Intent.CLARIFY,
            confidence=result.confidence,
            params=params,
            classifier_source="semantic_llm",
            language="en",
        )
    try:
        intent = Intent(result.intent)
    except ValueError:
        msg, params = semantic_to_clarification_request(
            text,
            SemanticUnderstanding(
                ambiguous=True,
                clarification=result.clarification,
                reasoning="invalid_intent_enum",
                llm_used=True,
            ),
        )
        return CommandRequest(
            raw_text=text,
            intent=Intent.CLARIFY,
            confidence=0.0,
            params=params,
            classifier_source="semantic_llm",
        )
    canonical = result.canonical_command or text
    req = CommandRequest(
        raw_text=canonical,
        intent=intent,
        confidence=result.confidence,
        classifier_source="semantic_llm",
        language="en",
    )
    if result.requires_confirmation:
        req = req.model_copy(update={"params": {"requires_confirmation": True}})
    return req


def _from_semantic_rules(
    text: str,
    *,
    normalized: str,
    ctx: SemanticContext,
) -> CommandRequest | None:
    sem = understand_semantic(text, normalized=normalized, context=ctx)
    _record_semantic(sem)
    if sem.meets_threshold():
        try:
            intent = Intent(sem.candidate_intent)
        except ValueError:
            return None
        return CommandRequest(
            raw_text=sem.canonical_command or text,
            intent=intent,
            confidence=sem.confidence,
            classifier_source=sem.source,
            language="en",
        )
    if sem.ambiguous or sem.confidence < SEMANTIC_MIN_CONFIDENCE:
        if sem.clarification:
            msg, params = semantic_to_clarification_request(text, sem)
            return CommandRequest(
                raw_text=text,
                intent=Intent.CLARIFY,
                confidence=sem.confidence,
                params=params,
                classifier_source="semantic",
                language="en",
            )
    return None


def classify_hybrid(
    text: str,
    session_context: object | None = None,
) -> tuple[CommandRequest, SemanticUnderstanding | None]:
    """
    A. exact rules / aliases (aliases resolved in router before this)
    B. grammar matcher (inside classify_rules / _match_special)
    C. semantic matcher
    D. optional semantic LLM
    Then legacy LLM classifier if configured.
    """
    from brain.intent_classifier import classify_rules, _session_to_context
    from brain.llm_intent_classifier import LLMIntentClassifier, classification_to_request

    corrected, _ = correct_tokens(text)
    normalized = _normalize(corrected)
    ctx = build_semantic_context(session_context)

    # A + B
    rule_req = classify_rules(corrected)
    if (
        rule_req.confidence >= CONFIDENCE_THRESHOLD
        and rule_req.intent not in (Intent.UNKNOWN, Intent.CLARIFY)
    ):
        _record_semantic(
            SemanticUnderstanding(
                candidate_intent=rule_req.intent.value,
                confidence=rule_req.confidence,
                canonical_command=corrected,
                reasoning="rules_or_grammar",
                source=rule_req.classifier_source,
                raw_transcript=text,
                normalized_transcript=normalized,
                final_routed_intent=rule_req.intent.value,
            )
        )
        set_final_routed_intent(rule_req.intent.value)
        return rule_req, _last_hybrid_semantic

    sem_req: CommandRequest | None = None
    if cfg.SEMANTIC_UNDERSTANDING_ENABLED:
        sem_req = _from_semantic_rules(corrected, normalized=normalized, ctx=ctx)
        if sem_req is not None and sem_req.intent not in (
            Intent.UNKNOWN,
            Intent.CLARIFY,
        ):
            set_final_routed_intent(sem_req.intent.value)
            return sem_req, _last_hybrid_semantic

    if cfg.SEMANTIC_LLM_ENABLED:
        llm_req = _from_semantic_llm(corrected, normalized=normalized, ctx=ctx)
        if llm_req is not None:
            set_final_routed_intent(llm_req.intent.value)
            return llm_req, _last_hybrid_semantic

    if LLM_CLASSIFIER_ENABLED:
        llm = LLMIntentClassifier()
        ic = llm.classify(corrected, session_context=_session_to_context(session_context))
        if ic.valid:
            req = classification_to_request(corrected, ic)
            set_final_routed_intent(req.intent.value)
            _record_semantic(
                SemanticUnderstanding(
                    candidate_intent=req.intent.value,
                    confidence=req.confidence,
                    canonical_command=corrected,
                    reasoning=ic.reason,
                    source="llm_classifier",
                    llm_used=True,
                    raw_transcript=text,
                    normalized_transcript=normalized,
                    final_routed_intent=req.intent.value,
                )
            )
            return req, _last_hybrid_semantic
        if LLM_FALLBACK_TO_RULES and rule_req.intent not in (Intent.UNKNOWN,):
            set_final_routed_intent(rule_req.intent.value)
            return rule_req.model_copy(update={"classifier_source": "fallback"}), _last_hybrid_semantic
        if not ic.valid:
            msg = ic.reason or "Please clarify."
            set_final_routed_intent(Intent.CLARIFY.value)
            return (
                CommandRequest(
                    raw_text=corrected,
                    intent=Intent.CLARIFY,
                    confidence=ic.confidence,
                    params={"clarification": msg},
                    classifier_source="clarification",
                ),
                _last_hybrid_semantic,
            )

    set_final_routed_intent(rule_req.intent.value)
    return rule_req, _last_hybrid_semantic
