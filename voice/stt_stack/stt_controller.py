"""Phase 42 STT orchestrator — multi-backend, fusion, retry, repair."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from config import (
    STT_FUSION_ENABLED,
    STT_STACK_ENABLED,
)
from core.logger import setup_logger
from voice.stt_engines.base import PartialCallback, SttHypothesis
from voice.stt_engines.registry import get_stt_engine_chain
from voice.stt_stack.audio_enhance import cleanup_enhanced_copy, enhance_audio_file
from voice.stt_stack.confidence_fusion import fuse_hypotheses
from voice.stt_stack.intent_correction import apply_intent_corrections
from voice.stt_stack.language_detect import resolve_transcription_language
from voice.stt_stack.partial_stream import make_partial_callback
from voice.stt_stack.retry_pipeline import run_with_retries
from voice.stt_stack.transcript_repair import repair_transcript
from voice.stt_stack.voice_fingerprint import adapt_from_audio, grammar_min_score_for_user
from voice.transcriber import TranscriptionResult, _evaluate_confidence

logger = setup_logger("jarvis.voice.stt.controller")


def _collect_from_engines(
    audio_path: Path,
    *,
    language: str,
    on_partial: PartialCallback | None,
    attempt: int = 0,
) -> list[SttHypothesis]:
    chain = get_stt_engine_chain()
    if not chain:
        return []
    hypotheses: list[SttHypothesis] = []
    start_idx = min(attempt, len(chain) - 1) if chain else 0
    try:
        from services.high_performance_runtime import get_acceleration_profile

        profile = get_acceleration_profile()
        if profile.gpu_enabled:
            chain = sorted(
                chain,
                key=lambda eng: 0 if getattr(eng.capabilities(), "gpu", False) else 1,
            )
        batch_size = profile.batch_size
    except Exception:
        batch_size = 2
    engines_to_run = (
        chain[start_idx:]
        if attempt > 0
        else chain[: max(1, batch_size)] if STT_FUSION_ENABLED
        else chain[:1]
    )
    for eng in engines_to_run:
        if not eng.is_available():
            continue
        try:
            h = eng.transcribe(audio_path, language=language, on_partial=on_partial)
            if h.text.strip():
                hypotheses.append(h)
        except Exception as exc:
            logger.warning("STT engine %s failed: %s", eng.name, exc)
    return hypotheses


def transcribe_with_stack(
    path: Path | str,
    *,
    on_partial: PartialCallback | None = None,
) -> TranscriptionResult:
    """Full Phase 42 pipeline when STT_STACK_ENABLED."""
    audio_path = Path(path)
    enhanced = enhance_audio_file(audio_path)
    partial_cb = on_partial or make_partial_callback()

    def _run(path_in: Path, *, language: str, on_partial: PartialCallback | None, attempt: int):
        return _collect_from_engines(
            path_in, language=language, on_partial=on_partial, attempt=attempt
        )

    lang = resolve_transcription_language()
    fused, all_hyps, attempts = run_with_retries(
        _run,
        enhanced,
        language=lang,
        on_partial=partial_cb,
    )
    if STT_FUSION_ENABLED and len(all_hyps) > 1:
        fused = fuse_hypotheses(all_hyps)

    text = fused.text
    repaired, _ = repair_transcript(text)
    corrected, _ = apply_intent_corrections(repaired)
    final_text = corrected

    try:
        from faster_whisper.audio import decode_audio
        import numpy as np

        adapt_from_audio(np.squeeze(decode_audio(str(audio_path))).astype(np.float32))
    except Exception:
        pass

    low, rec = _evaluate_confidence(fused.avg_logprob, fused.language_probability, fused.language)
    if fused.confidence >= 0.75:
        low = False
        rec = None

    backends = sorted({h.engine for h in all_hyps}) if all_hyps else [fused.engine]
    cleanup_enhanced_copy(enhanced, audio_path)

    return TranscriptionResult(
        text=final_text,
        language=fused.language or lang,
        model=fused.engine,
        device="stack",
        compute_type="fusion" if STT_FUSION_ENABLED else "single",
        avg_logprob=fused.avg_logprob,
        language_probability=fused.language_probability,
        low_confidence=low,
        recommendation=rec,
        backends_used=backends,
        fused_confidence=fused.confidence,
        repair_applied=final_text != text,
        retry_attempts=attempts,
        grammar_min_score=grammar_min_score_for_user(),
    )


def is_stack_enabled() -> bool:
    return bool(STT_STACK_ENABLED)
