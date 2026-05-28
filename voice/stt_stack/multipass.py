"""Multi-pass local STT understanding (Phase 42 v2)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from config import (
    STT_ACCURATE_RETRY_BEAM_SIZE,
    STT_ACCURATE_RETRY_MAX_MS,
    STT_MULTIPASS_ENABLED,
    STT_RETRY_ON_UNKNOWN,
)
from core.logger import setup_logger
from voice.stt_stack.partial_stream import PartialCallback, make_partial_callback
from voice.stt_stack.transcript_repair import repair_transcript
from voice.transcriber import TranscriptionResult, _evaluate_confidence

logger = setup_logger("jarvis.voice.stt.multipass")

_last_multipass: "MultipassTrace | None" = None


@dataclass
class MultipassTrace:
    raw_transcript: str = ""
    normalized_transcript: str = ""
    grammar_corrected_transcript: str = ""
    grammar_command: str = ""
    grammar_confidence: float = 0.0
    grammar_correction_reason: str = ""
    retry_reason: str = ""
    pass_latencies_ms: dict[str, float] = field(default_factory=dict)
    accurate_retry_used: bool = False


def get_last_multipass_trace() -> MultipassTrace | None:
    return _last_multipass


def is_multipass_enabled() -> bool:
    return bool(STT_MULTIPASS_ENABLED)


def _preview_intent_unknown(text: str) -> bool:
    try:
        from brain.intent_classifier import classify_rules

        req = classify_rules(text)
        return req.intent.value == "unknown"
    except Exception:
        return True


def _close_match_detected(text: str, *, min_score: int) -> bool:
    try:
        from brain.command_grammar import score_command_grammar

        match = score_command_grammar(text, min_score=min_score)
        if match is None:
            return False
        return 75 <= match.fuzzy_score < min_score
    except Exception:
        return False


def _should_accurate_retry(
    *,
    text: str,
    low_confidence: bool,
    empty: bool,
    unknown_intent: bool,
    close_match: bool,
) -> bool:
    if not STT_RETRY_ON_UNKNOWN:
        return low_confidence or empty
    if empty or low_confidence:
        return True
    if unknown_intent:
        return True
    if close_match:
        return True
    return False


def transcribe_multipass(
    audio_path: Path | str,
    *,
    on_partial: PartialCallback | None = None,
) -> TranscriptionResult:
    """
    Fast STT → repair/grammar → optional accurate retry (same buffer, higher beam).
    """
    global _last_multipass
    path = Path(audio_path)
    trace = MultipassTrace()
    partial_cb = on_partial or make_partial_callback()

    t0 = time.perf_counter()
    from voice.transcriber import transcribe_faster_whisper_hypothesis

    fast = transcribe_faster_whisper_hypothesis(
        path, language=_language(), on_partial=partial_cb, beam_size=None
    )
    trace.pass_latencies_ms["fast"] = (time.perf_counter() - t0) * 1000.0
    trace.raw_transcript = fast.text

    t1 = time.perf_counter()
    normalized, _ = repair_transcript(fast.text)
    trace.normalized_transcript = normalized
    trace.pass_latencies_ms["repair"] = (time.perf_counter() - t1) * 1000.0

    t2 = time.perf_counter()
    final_text, grammar = _apply_grammar_and_aliases(normalized)
    trace.grammar_corrected_transcript = final_text
    if grammar is not None:
        trace.grammar_command = grammar.best_command
        trace.grammar_confidence = grammar.confidence
        trace.grammar_correction_reason = grammar.correction_reason
    trace.pass_latencies_ms["grammar"] = (time.perf_counter() - t2) * 1000.0

    low, rec = _evaluate_confidence(fast.avg_logprob, fast.language_probability, fast.language)
    try:
        from voice.stt_stack.voice_fingerprint import grammar_min_score_for_user

        min_score = grammar_min_score_for_user()
    except Exception:
        from config import VOICE_GRAMMAR_MIN_SCORE

        min_score = VOICE_GRAMMAR_MIN_SCORE

    unknown = _preview_intent_unknown(final_text)
    close = _close_match_detected(final_text, min_score=min_score)
    empty = not (final_text or "").strip()

    if _should_accurate_retry(
        text=final_text,
        low_confidence=low,
        empty=empty,
        unknown_intent=unknown,
        close_match=close,
    ):
        reason_parts = []
        if empty:
            reason_parts.append("empty")
        if low:
            reason_parts.append("low_confidence")
        if unknown:
            reason_parts.append("unknown_intent")
        if close:
            reason_parts.append("close_match")
        trace.retry_reason = ",".join(reason_parts) or "retry_policy"
        t3 = time.perf_counter()
        try:
            accurate = transcribe_faster_whisper_hypothesis(
                path,
                language=fast.language,
                on_partial=None,
                beam_size=STT_ACCURATE_RETRY_BEAM_SIZE,
                max_ms=STT_ACCURATE_RETRY_MAX_MS,
            )
            trace.accurate_retry_used = True
            trace.pass_latencies_ms["accurate"] = (time.perf_counter() - t3) * 1000.0
            if (accurate.text or "").strip():
                normalized2, _ = repair_transcript(accurate.text)
                final2, grammar2 = _apply_grammar_and_aliases(normalized2)
                if len(final2.strip()) >= len(final_text.strip()):
                    final_text = final2
                    trace.normalized_transcript = normalized2
                    trace.grammar_corrected_transcript = final2
                    fast = accurate
                    if grammar2 is not None:
                        trace.grammar_command = grammar2.best_command
                        trace.grammar_confidence = grammar2.confidence
                        trace.grammar_correction_reason = grammar2.correction_reason
                low, rec = _evaluate_confidence(
                    accurate.avg_logprob,
                    accurate.language_probability,
                    accurate.language,
                )
        except Exception as exc:
            logger.warning("accurate STT retry failed: %s", exc)
            trace.pass_latencies_ms["accurate"] = (time.perf_counter() - t3) * 1000.0

    _last_multipass = trace
    _record_debug(trace, final_text, low_confidence=low)

    return TranscriptionResult(
        text=final_text,
        language=fast.language,
        model="multipass/faster_whisper",
        device="local",
        compute_type="multipass",
        avg_logprob=fast.avg_logprob,
        language_probability=fast.language_probability,
        low_confidence=low,
        recommendation=rec,
        backends_used=["faster_whisper"],
        fused_confidence=fast.confidence if hasattr(fast, "confidence") else None,
        repair_applied=final_text != trace.raw_transcript,
        retry_attempts=2 if trace.accurate_retry_used else 1,
    )


def _language() -> str:
    from voice.stt_stack.language_detect import resolve_transcription_language

    return resolve_transcription_language()


def _apply_grammar_and_aliases(text: str):
    from brain.command_grammar import apply_grammar_correction
    from voice.voice_calibration import apply_calibration_corrections

    corrected = apply_calibration_corrections(text)
    final, match = apply_grammar_correction(
        corrected,
        min_score=_grammar_min_score(),
    )
    try:
        from brain.aliases import resolve_alias

        alias = resolve_alias(final)
        if alias is not None and alias.intent.value != "unknown":
            final = alias.raw_text or final
    except Exception:
        pass
    return final, match


def _grammar_min_score() -> int:
    try:
        from voice.stt_stack.voice_fingerprint import grammar_min_score_for_user

        return grammar_min_score_for_user()
    except Exception:
        from config import VOICE_GRAMMAR_MIN_SCORE

        return VOICE_GRAMMAR_MIN_SCORE


def _record_debug(trace: MultipassTrace, final_text: str, *, low_confidence: bool) -> None:
    try:
        from voice.voice_debug_store import record_voice_understanding

        record_voice_understanding(
            raw=trace.raw_transcript,
            normalized=trace.normalized_transcript,
            grammar_corrected=trace.grammar_corrected_transcript or final_text,
            grammar_command=trace.grammar_command,
            grammar_confidence=trace.grammar_confidence,
            grammar_reason=trace.grammar_correction_reason,
            retry_reason=trace.retry_reason,
            pass_latencies_ms=dict(trace.pass_latencies_ms),
            low_confidence=low_confidence,
        )
    except Exception:
        pass
