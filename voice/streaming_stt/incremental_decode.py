"""Incremental decode on rolling buffer windows (local STT, no cloud)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.streaming.decode")

TranscribeFn = Callable[[np.ndarray, int], str]


@dataclass
class IncrementalDecodeState:
    text: str = ""
    last_decode_monotonic: float = 0.0
    last_generation: int = -1
    decode_count: int = 0


def _merge_incremental(previous: str, new: str) -> str:
    prev = (previous or "").strip()
    nxt = (new or "").strip()
    if not nxt:
        return prev
    if not prev:
        return nxt
    if nxt.startswith(prev):
        return nxt
    if prev.startswith(nxt):
        return prev
    # Longest common prefix stability
    common = 0
    for a, b in zip(prev.split(), nxt.split()):
        if a == b:
            common += 1
        else:
            break
    if common > 0:
        stable = " ".join(nxt.split()[:common])
        tail = " ".join(nxt.split()[common:])
        if tail:
            return f"{stable} {tail}".strip()
    return nxt


class IncrementalDecoder:
    """
    Decode only when the rolling buffer advances enough (time + new audio).
    Uses a short-window transcribe on the full rolling snapshot (fast beam=1).
    """

    def __init__(
        self,
        *,
        transcribe_fn: TranscribeFn,
        min_interval_ms: float = 150.0,
        min_new_samples: int = 1600,
    ) -> None:
        self._transcribe = transcribe_fn
        self._min_interval_s = max(0.05, min_interval_ms / 1000.0)
        self._min_new_samples = max(400, min_new_samples)
        self._state = IncrementalDecodeState()
        self._samples_at_last_decode = 0

    @property
    def text(self) -> str:
        return self._state.text

    def should_decode(self, *, total_samples: int, generation: int) -> bool:
        if generation == self._state.last_generation:
            return False
        now = time.monotonic()
        if now - self._state.last_decode_monotonic < self._min_interval_s:
            return False
        if total_samples - self._samples_at_last_decode < self._min_new_samples:
            return False
        return True

    def decode(self, audio: np.ndarray, *, sample_rate: int, generation: int) -> str:
        if audio.size == 0:
            return self._state.text
        t0 = time.perf_counter()
        try:
            new_text = self._transcribe(audio, sample_rate)
        except Exception as exc:
            from voice.streaming_stt.session_policy import StreamingSttFallbackError

            if isinstance(exc, StreamingSttFallbackError):
                raise
            logger.debug("incremental decode failed: %s", exc)
            return self._state.text
        merged = _merge_incremental(self._state.text, new_text)
        self._state.text = merged
        self._state.last_decode_monotonic = time.monotonic()
        self._state.last_generation = generation
        self._state.decode_count += 1
        self._samples_at_last_decode = audio.shape[0]
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        logger.debug(
            "incremental decode #%s gen=%s ms=%.0f chars=%s",
            self._state.decode_count,
            generation,
            elapsed_ms,
            len(merged),
        )
        return merged


def default_transcribe_fn(audio: np.ndarray, sample_rate: int) -> str:
    """Fast partial pass only (no accurate retry / multipass)."""
    from voice.streaming_stt.transcribe import transcribe_stream_partial

    return transcribe_stream_partial(audio, sample_rate)
