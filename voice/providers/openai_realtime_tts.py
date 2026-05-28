"""OpenAI realtime streaming TTS — primary low-latency provider (Phase 57)."""

from __future__ import annotations

import os
import time
from typing import Iterator

from voice.engines.base import SynthesisChunk
from voice.providers.base import ProviderHealth, RealtimeTtsProvider, SpeechProsody
from voice.providers.streaming_base import CancellableStreamMixin


class OpenAIRealtimeTtsProvider(CancellableStreamMixin, RealtimeTtsProvider):
    name = "openai_realtime"
    fallback_only = False

    def __init__(self) -> None:
        self._init_stream_state()

    def _api_key(self) -> str:
        return (os.getenv("OPENAI_API_KEY") or "").strip()

    def _voice(self, voice: str) -> str:
        return (voice or os.getenv("OPENAI_TTS_VOICE") or "alloy").strip()

    def _model(self) -> str:
        return (os.getenv("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts").strip()

    def is_available(self) -> bool:
        return bool(self._api_key())

    def health(self) -> ProviderHealth:
        if self.is_available():
            return ProviderHealth(
                name=self.name,
                available=True,
                latency_class="low",
                reason="openai_api_key_set",
            )
        return ProviderHealth(
            name=self.name,
            available=False,
            reason="OPENAI_API_KEY missing",
        )

    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        del rate_raw, prosody
        if not text.strip():
            return
        if not self.is_available():
            raise RuntimeError("OpenAI TTS not configured")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc

        self._init_stream_state()
        self._stream_t0 = time.perf_counter()
        t0 = self._stream_t0
        client = OpenAI(api_key=self._api_key())
        first = True
        chunk_size = int(os.getenv("OPENAI_TTS_STREAM_CHUNK_BYTES", "2048"))

        with client.audio.speech.with_streaming_response.create(
            model=self._model(),
            voice=self._voice(voice),
            input=text,
            response_format="mp3",
        ) as response:
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                if self._stream_cancelled():
                    break
                if not chunk:
                    continue
                hint = 0.85 if first else 0.55
                if first:
                    first = False
                    self._last_first_chunk_ms = (time.perf_counter() - t0) * 1000.0
                yield SynthesisChunk(data=chunk, mime="audio/mpeg", viseme_hint=hint)


# Backward-compatible alias
OpenAIRealtimeProvider = OpenAIRealtimeTtsProvider
