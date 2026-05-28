"""Shared cancellable streaming helpers for realtime TTS providers."""

from __future__ import annotations

import threading
import time
from typing import Iterator

from voice.engines.base import SynthesisChunk
from voice.streaming_player import is_stop_requested


class CancellableStreamMixin:
    """Mixin: cooperative cancel + first-chunk latency tracking."""

    _cancel_event: threading.Event
    _last_first_chunk_ms: float | None
    _last_first_audio_ms: float | None

    def _init_stream_state(self) -> None:
        self._cancel_event = threading.Event()
        self._last_first_chunk_ms = None
        self._last_first_audio_ms = None

    def cancel(self) -> None:
        self._cancel_event.set()
        from voice.streaming_player import request_stop_speaking

        request_stop_speaking()

    def _stream_cancelled(self) -> bool:
        return self._cancel_event.is_set() or is_stop_requested()

    def last_time_to_first_audio_ms(self) -> float | None:
        return self._last_first_audio_ms or self._last_first_chunk_ms

    def mark_first_audio_playback(self) -> None:
        if self._last_first_audio_ms is None:
            self._last_first_audio_ms = getattr(self, "_stream_t0", time.perf_counter())
            if hasattr(self, "_stream_t0"):
                self._last_first_audio_ms = (time.perf_counter() - self._stream_t0) * 1000.0

    def _yield_chunk(
        self,
        data: bytes,
        *,
        mime: str = "audio/mpeg",
        viseme_hint: float = 0.6,
        t0: float,
        first: bool,
    ) -> Iterator[SynthesisChunk]:
        if not data or self._stream_cancelled():
            return
        if first and self._last_first_chunk_ms is None:
            self._last_first_chunk_ms = (time.perf_counter() - t0) * 1000.0
        yield SynthesisChunk(data=data, mime=mime, viseme_hint=viseme_hint)
