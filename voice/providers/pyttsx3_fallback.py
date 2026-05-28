"""pyttsx3 emergency fallback provider (Phase 57)."""

from __future__ import annotations

import time
from typing import Iterator

from voice.engines.base import SynthesisChunk
from voice.providers.base import ProviderHealth, RealtimeTtsProvider, SpeechProsody


class Pyttsx3FallbackProvider(RealtimeTtsProvider):
    name = "pyttsx3_fallback"
    fallback_only = True

    def is_available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401

            return True
        except ImportError:
            return False

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name,
            available=self.is_available(),
            fallback_only=True,
            latency_class="high",
            reason="emergency_fallback_only" if self.is_available() else "pyttsx3 missing",
        )

    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        del voice, prosody
        if not text.strip():
            return
        import config as cfg
        from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER

        t0 = time.perf_counter()
        NORMAL_DIRECT_SPEAKER(
            text,
            rate_raw=rate_raw or cfg.TTS_RATE_RAW,
            record_user_success=False,
        )
        self._last_first_ms = (time.perf_counter() - t0) * 1000.0
        self._last_total_ms = self._last_first_ms
        yield SynthesisChunk(data=b"", mime="audio/direct", viseme_hint=0.5)

    _last_first_ms: float | None = None
    _last_total_ms: float | None = None

    def last_time_to_first_audio_ms(self) -> float | None:
        return self._last_first_ms

    def last_total_playback_ms(self) -> float | None:
        return self._last_total_ms
