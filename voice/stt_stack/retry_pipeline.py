"""Automatic STT retry when confidence is low."""

from __future__ import annotations

from pathlib import Path

from config import STT_RETRY_MAX_ATTEMPTS, STT_LOW_CONFIDENCE_LOGPROB
from voice.stt_engines.base import PartialCallback, SttHypothesis
from voice.stt_stack.confidence_fusion import fuse_hypotheses

LOW_CONF_THRESHOLD = 0.52


def _is_low_confidence(h: SttHypothesis) -> bool:
    if h.confidence < LOW_CONF_THRESHOLD:
        return True
    if h.avg_logprob is not None and h.avg_logprob < STT_LOW_CONFIDENCE_LOGPROB:
        return True
    return not (h.text or "").strip()


def run_with_retries(
    transcribe_fn,
    audio_path: Path,
    *,
    language: str,
    on_partial: PartialCallback | None,
    max_attempts: int | None = None,
) -> tuple[SttHypothesis, list[SttHypothesis], int]:
    """
    Invoke transcribe_fn(engine) per attempt; collect hypotheses for fusion.
    Returns (best_fused, all_hypotheses, attempts_used).
    """
    attempts = max(1, max_attempts or STT_RETRY_MAX_ATTEMPTS)
    collected: list[SttHypothesis] = []
    for attempt in range(attempts):
        batch = transcribe_fn(audio_path, language=language, on_partial=on_partial, attempt=attempt)
        if isinstance(batch, SttHypothesis):
            batch = [batch]
        collected.extend(batch)
        fused = fuse_hypotheses(collected)
        if not _is_low_confidence(fused):
            return fused, collected, attempt + 1
    return fuse_hypotheses(collected), collected, attempts
