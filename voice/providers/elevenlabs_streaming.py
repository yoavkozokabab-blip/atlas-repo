"""ElevenLabs streaming TTS provider (Phase 57/58 — websocket primary)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Iterator

from voice.engines.base import SynthesisChunk
from voice.providers.base import ProviderHealth, RealtimeTtsProvider, SpeechProsody
from voice.providers.streaming_base import CancellableStreamMixin


class ElevenLabsStreamingProvider(CancellableStreamMixin, RealtimeTtsProvider):
    name = "elevenlabs"
    fallback_only = False

    def __init__(self) -> None:
        self._init_stream_state()

    def _api_key(self) -> str:
        return (os.getenv("ELEVENLABS_API_KEY") or "").strip()

    def _voice_id(self, voice: str) -> str:
        return (voice or os.getenv("ELEVENLABS_VOICE_ID") or "").strip()

    def _use_websocket(self) -> bool:
        try:
            import config as cfg

            return bool(getattr(cfg, "ELEVENLABS_WEBSOCKET_ENABLED", True))
        except Exception:
            return True

    def is_available(self) -> bool:
        return bool(self._api_key() and self._voice_id(""))

    def health(self) -> ProviderHealth:
        if self.is_available():
            transport = "websocket" if self._use_websocket() else "http"
            return ProviderHealth(
                name=self.name,
                available=True,
                latency_class="low",
                reason=f"elevenlabs_{transport}_configured",
            )
        missing = []
        if not self._api_key():
            missing.append("ELEVENLABS_API_KEY")
        if not self._voice_id(""):
            missing.append("ELEVENLABS_VOICE_ID")
        return ProviderHealth(
            name=self.name,
            available=False,
            reason=f"missing {','.join(missing) or 'config'}",
        )

    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        del rate_raw
        if not text.strip():
            return
        if not self.is_available():
            raise RuntimeError("ElevenLabs not configured")

        if self._use_websocket():
            from voice.providers.elevenlabs_websocket import get_elevenlabs_ws_session

            session = get_elevenlabs_ws_session()
            self._stream_t0 = time.perf_counter()
            connect_ms = session.last_connect_ms
            if connect_ms is not None:
                self._last_connect_ms = connect_ms
            for chunk in session.stream(text, voice=voice, prosody=prosody):
                if self._stream_cancelled():
                    session.cancel()
                    break
                if chunk.data and self._last_first_chunk_ms is None:
                    self._last_first_chunk_ms = session.last_first_byte_ms or (
                        (time.perf_counter() - self._stream_t0) * 1000.0
                    )
                yield chunk
            return

        yield from self._stream_http(text, voice=voice, prosody=prosody)

    _last_connect_ms: float | None = None

    def last_provider_connect_ms(self) -> float | None:
        return self._last_connect_ms

    def _stream_http(
        self,
        text: str,
        *,
        voice: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        voice_id = self._voice_id(voice)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        payload = {
            "text": text,
            "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5"),
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.75,
                "style": 0.35 if (prosody and prosody.emotion != "neutral") else 0.2,
                "use_speaker_boost": True,
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self._api_key(),
            },
            method="POST",
        )
        t0 = time.perf_counter()
        self._stream_t0 = t0
        first = True
        with urllib.request.urlopen(req, timeout=30) as resp:
            while True:
                if self._stream_cancelled():
                    break
                chunk = resp.read(4096)
                if not chunk:
                    break
                if first:
                    first = False
                    self._last_first_chunk_ms = (time.perf_counter() - t0) * 1000.0
                yield SynthesisChunk(data=chunk, mime="audio/mpeg", viseme_hint=0.7)

    def last_time_to_first_audio_ms(self) -> float | None:
        return self._last_first_chunk_ms
