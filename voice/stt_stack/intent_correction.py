"""Command intent correction on noisy transcripts (Phase 42)."""

from __future__ import annotations

from config import STT_INTENT_CORRECTION_ENABLED
from voice.stt_stack.voice_fingerprint import grammar_min_score_for_user
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stt.intent_correction")

# Common mis-hearings → canonical command phrase (grammar will match intent)
_CORRECTIONS: list[tuple[str, str]] = [
    ("run diagnostic", "run diagnostics"),
    ("open dash board", "open dashboard"),
    ("show dash board", "show dashboard"),
    ("show jar vis status", "show jarvis status"),
    ("benchmark speech", "benchmark stt"),
    ("list speech engines", "list stt engines"),
    ("stop talking", "stop speaking"),
]


def apply_intent_corrections(text: str) -> tuple[str, bool]:
    """
    Normalize transcript toward known command phrases before classification.
    Returns (text, changed).
    """
    if not STT_INTENT_CORRECTION_ENABLED or not text.strip():
        return text, False
    lower = " ".join(text.lower().split())
    changed = False
    for wrong, right in _CORRECTIONS:
        if wrong in lower:
            lower = lower.replace(wrong, right)
            changed = True
    try:
        from brain.voice_grammar import match_voice_grammar

        req = match_voice_grammar(lower, min_score=grammar_min_score_for_user())
        if req is not None and req.raw_text:
            canonical = " ".join(req.raw_text.lower().split())
            if canonical != lower:
                lower = canonical
                changed = True
    except Exception as exc:
        logger.debug("grammar correction skipped: %s", exc)
    return lower.strip(), changed
