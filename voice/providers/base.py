"""Realtime TTS provider protocol (Phase 57)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator

from voice.engines.base import SynthesisChunk


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    available: bool
    fallback_only: bool = False
    latency_class: str = "medium"
    reason: str = ""


@dataclass
class ProviderLatency:
    provider: str
    time_to_first_audio_ms: float | None = None
    provider_latency_ms: float | None = None
    total_playback_ms: float | None = None
    queue_wait_ms: float | None = None
    interruption_latency_ms: float | None = None


@dataclass
class SpeechProsody:
    """Lightweight pacing hints for natural delivery."""

    emotion: str = "neutral"
    speed: float = 1.0
    pause_before_ms: int = 0
    pause_after_ms: int = 0
    breath_pause: bool = False


class RealtimeTtsProvider(ABC):
    name: str = "base"
    fallback_only: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def health(self) -> ProviderHealth:
        pass

    @abstractmethod
    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        pass

    def cancel(self) -> None:
        from voice.streaming_player import request_stop_speaking

        request_stop_speaking()

    def speak_stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ):
        """Return streaming synthesis chunks (alias for stream())."""
        return self.stream(text, voice=voice, rate_raw=rate_raw, prosody=prosody)

    def availability_reason(self) -> str:
        if self.is_available():
            return "available"
        return self.health().reason or "not configured"
