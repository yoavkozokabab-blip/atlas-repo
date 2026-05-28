"""Semantic command understanding — suggests intents; router executes."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import config as cfg
from config import IMPLEMENTED_INTENTS
from core.logger import setup_logger
from core.types import Intent
from language.semantic_context import SemanticContext

logger = setup_logger("jarvis.language.semantic")

_last_understanding: SemanticUnderstanding | None = None


@dataclass
class SemanticUnderstanding:
    """Structured semantic layer output (no execution)."""

    candidate_intent: str = ""
    confidence: float = 0.0
    canonical_command: str = ""
    reasoning: str = ""
    ambiguous: bool = False
    clarification: str | None = None
    alternatives: tuple[str, ...] = ()
    source: str = "none"
    llm_used: bool = False
    raw_transcript: str = ""
    normalized_transcript: str = ""
    final_routed_intent: str = ""

    def meets_threshold(self) -> bool:
        return (
            bool(self.candidate_intent)
            and self.candidate_intent in IMPLEMENTED_INTENTS
            and self.confidence >= cfg.SEMANTIC_MIN_CONFIDENCE
            and not self.ambiguous
        )


def get_last_semantic_understanding() -> SemanticUnderstanding | None:
    return _last_understanding


def set_final_routed_intent(intent_value: str) -> None:
    global _last_understanding
    if _last_understanding is not None:
        _last_understanding.final_routed_intent = intent_value


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _record(u: SemanticUnderstanding) -> SemanticUnderstanding:
    global _last_understanding
    _last_understanding = u
    return u


@dataclass(frozen=True)
class _NLPattern:
    pattern: re.Pattern[str]
    intent: str
    canonical: str
    confidence: float
    reason: str


def _nl_patterns() -> list[_NLPattern]:
    return [
        _NLPattern(
            re.compile(r"what(?:'s| is) going on(?: here)?"),
            Intent.WHAT_AM_I_DOING.value,
            "what am i doing",
            0.88,
            "natural_status_phrase",
        ),
        _NLPattern(
            re.compile(r"show me what failed|what failed|what(?:'s| is) failing"),
            Intent.SHOW_FAILING_TESTS.value,
            "show failing tests",
            0.86,
            "failure_context_phrase",
        ),
        _NLPattern(
            re.compile(r"why did (?:this|it) fail|explain (?:this|the) (?:error|failure)"),
            Intent.EXPLAIN_THIS_ERROR.value,
            "explain this error",
            0.87,
            "error_explanation_phrase",
        ),
        _NLPattern(
            re.compile(r"check (?:this|the) project|what(?:'s| is) wrong with (?:this|the) project"),
            Intent.RUN_DIAGNOSTICS.value,
            "run diagnostics",
            0.78,
            "project_check_phrase",
        ),
        _NLPattern(
            re.compile(r"what can you do|what are you able to do"),
            Intent.SHOW_CAPABILITIES.value,
            "show capabilities",
            0.9,
            "capabilities_phrase",
        ),
        _NLPattern(
            re.compile(r"how are you doing|system health|is everything ok"),
            Intent.SHOW_SYSTEM_STATUS.value,
            "show system status",
            0.82,
            "health_phrase",
        ),
        _NLPattern(
            re.compile(r"run (?:a )?diagnostic|check (?:the )?system"),
            Intent.RUN_DIAGNOSTICS.value,
            "run diagnostics",
            0.84,
            "diagnostics_phrase",
        ),
    ]


def _contextual_resolve(normalized: str, ctx: SemanticContext) -> SemanticUnderstanding | None:
    last = (ctx.last_intent or "").lower()
    if normalized in {"open it", "open that", "open this"}:
        if "report" in last:
            return SemanticUnderstanding(
                candidate_intent=Intent.SHOW_LATEST_LIVE_REPORT.value,
                confidence=0.8,
                canonical_command="show latest live report",
                reasoning="context_open_after_report",
                source="semantic_context",
                raw_transcript=normalized,
                normalized_transcript=normalized,
            )
        if "dashboard" in last:
            return SemanticUnderstanding(
                candidate_intent=Intent.OPEN_TRADING_DASHBOARD.value,
                confidence=0.78,
                canonical_command="open dashboard",
                reasoning="context_open_after_dashboard",
                source="semantic_context",
                raw_transcript=normalized,
                normalized_transcript=normalized,
            )
    if normalized in {"show it", "show that", "show this again"}:
        if "failing" in last or "test" in last:
            return SemanticUnderstanding(
                candidate_intent=Intent.SHOW_FAILING_TESTS.value,
                confidence=0.82,
                canonical_command="show failing tests",
                reasoning="context_show_after_tests",
                source="semantic_context",
                raw_transcript=normalized,
                normalized_transcript=normalized,
            )
    if ctx.extra.get("ide_active") and normalized in {
        "what's going on here",
        "whats going on here",
        "what am i working on",
    }:
        return SemanticUnderstanding(
            candidate_intent=Intent.WHAT_AM_I_DOING.value,
            confidence=0.85,
            canonical_command="what am i doing",
            reasoning="ide_active_context",
            source="semantic_context",
            raw_transcript=normalized,
            normalized_transcript=normalized,
        )
    return None


def _fuzzy_semantic_match(normalized: str) -> SemanticUnderstanding | None:
    try:
        from rapidfuzz import fuzz
        from brain.command_grammar import list_grammar_phrases
    except ImportError:
        return None

    phrases = list_grammar_phrases()
    if not phrases:
        return None
    best_phrase = ""
    best_score = 0
    for phrase in phrases:
        score = int(fuzz.token_sort_ratio(normalized, phrase))
        if score > best_score:
            best_score = score
            best_phrase = phrase
    if best_score < 78:
        return None
    try:
        from brain.command_grammar import score_command_grammar

        match = score_command_grammar(normalized, min_score=78)
        if match is None:
            return None
        conf = min(0.92, (best_score / 100.0) * match.confidence)
        return SemanticUnderstanding(
            candidate_intent=match.intent.value,
            confidence=conf,
            canonical_command=match.corrected_text,
            reasoning=f"fuzzy_semantic:{match.correction_reason}",
            source="semantic_fuzzy",
            raw_transcript=normalized,
            normalized_transcript=normalized,
        )
    except Exception:
        return None


def _pattern_match(normalized: str, raw: str) -> SemanticUnderstanding | None:
    for entry in _nl_patterns():
        if entry.pattern.search(normalized):
            if entry.intent not in IMPLEMENTED_INTENTS:
                continue
            return SemanticUnderstanding(
                candidate_intent=entry.intent,
                confidence=entry.confidence,
                canonical_command=entry.canonical,
                reasoning=entry.reason,
                source="semantic_pattern",
                raw_transcript=raw,
                normalized_transcript=normalized,
            )
    return None


def _ambiguity_clarification(
    heard: str,
    options: list[tuple[str, str]],
) -> str:
    if len(options) >= 2:
        a, b = options[0][1], options[1][1]
        return f"I heard {heard!r}. Did you mean {a} or {b}?"
    if options:
        return f"I heard {heard!r}. Did you mean {options[0][1]}?"
    return f"I heard {heard!r}. Please rephrase or be more specific."


def understand_semantic(
    raw_transcript: str,
    *,
    normalized: str | None = None,
    context: SemanticContext | None = None,
) -> SemanticUnderstanding:
    """
    Semantic matcher (patterns, context, fuzzy).
    Does not execute — returns candidate intent + confidence only.
    """
    if not cfg.SEMANTIC_UNDERSTANDING_ENABLED:
        return _record(
            SemanticUnderstanding(
                reasoning="semantic_disabled",
                raw_transcript=raw_transcript,
                normalized_transcript=normalized or raw_transcript,
            )
        )

    from language.semantic_context import build_semantic_context

    ctx = context or build_semantic_context()
    norm = normalized if normalized is not None else _normalize(raw_transcript)
    if not norm:
        return _record(
            SemanticUnderstanding(
                ambiguous=True,
                clarification="I did not catch that. Please repeat your command.",
                reasoning="empty_transcript",
                raw_transcript=raw_transcript,
                normalized_transcript=norm,
            )
        )

    contextual = _contextual_resolve(norm, ctx)
    if contextual is not None:
        contextual.raw_transcript = raw_transcript
        return _record(contextual)

    pat = _pattern_match(norm, raw_transcript)
    if pat is not None and pat.confidence >= cfg.SEMANTIC_MIN_CONFIDENCE:
        return _record(pat)

    fuzzy = _fuzzy_semantic_match(norm)
    if fuzzy is not None:
        if fuzzy.confidence >= cfg.SEMANTIC_MIN_CONFIDENCE:
            fuzzy.raw_transcript = raw_transcript
            return _record(fuzzy)
        # close but below threshold — ask clarification with alternatives
        alts: list[tuple[str, str]] = []
        if fuzzy.candidate_intent:
            alts.append((fuzzy.candidate_intent, fuzzy.canonical_command))
        return _record(
            SemanticUnderstanding(
                candidate_intent=fuzzy.candidate_intent,
                confidence=fuzzy.confidence,
                canonical_command=fuzzy.canonical_command,
                reasoning="below_semantic_threshold",
                ambiguous=True,
                clarification=_ambiguity_clarification(
                    raw_transcript,
                    alts or [("", "a supported command")],
                ),
                alternatives=tuple(a[0] for a in alts),
                source="semantic_fuzzy",
                raw_transcript=raw_transcript,
                normalized_transcript=norm,
            )
        )

    # Multiple pattern near-misses → ambiguity
    near: list[tuple[str, str]] = []
    for entry in _nl_patterns():
        if entry.pattern.search(norm):
            near.append((entry.intent, entry.canonical))
    if len(near) >= 2:
        return _record(
            SemanticUnderstanding(
                ambiguous=True,
                clarification=_ambiguity_clarification(raw_transcript, near),
                alternatives=tuple(n[0] for n in near),
                reasoning="multiple_semantic_candidates",
                confidence=0.5,
                raw_transcript=raw_transcript,
                normalized_transcript=norm,
            )
        )

    return _record(
        SemanticUnderstanding(
            reasoning="no_semantic_match",
            ambiguous=True,
            clarification=f"I heard {raw_transcript!r}. Which command did you mean?",
            confidence=0.0,
            raw_transcript=raw_transcript,
            normalized_transcript=norm,
        )
    )


def semantic_to_clarification_request(
    text: str,
    sem: SemanticUnderstanding,
) -> tuple[str, dict]:
    """Build clarification message and params for CLARIFY intent."""
    msg = sem.clarification or "Please clarify your command."
    params: dict = {
        "clarification": msg,
        "heard": text[:200],
        "semantic_confidence": sem.confidence,
    }
    if sem.alternatives:
        params["alternatives"] = list(sem.alternatives)
    return msg, params
