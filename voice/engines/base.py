"""TTS engine protocol (Phase 41)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class VoiceInfo:
    engine: str
    voice_id: str
    label: str
    language: str = "en"
    gender: str = ""


@dataclass
class SynthesisChunk:
    """One audio chunk for streaming playback."""

    data: bytes
    mime: str = "audio/mpeg"
    viseme_hint: float = 0.5


@dataclass
class EngineCapabilities:
    streaming: bool = False
    neural: bool = False
    offline: bool = False


class TTSEngine(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if engine can run on this machine."""

    @abstractmethod
    def capabilities(self) -> EngineCapabilities:
        pass

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        pass

    def synthesize_file(
        self,
        text: str,
        *,
        voice: str,
        rate_raw: str,
        out_path: Path,
    ) -> None:
        """Write full utterance to out_path (blocking)."""
        raise NotImplementedError

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        rate_raw: str,
    ) -> Iterator[SynthesisChunk]:
        """Yield audio chunks; default: single file chunk."""
        raise NotImplementedError

    def availability_reason(self) -> str:
        if self.is_available():
            return "available"
        return "not configured or dependency missing"
