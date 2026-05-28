"""STT engine protocol (Phase 42)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PartialCallback = Callable[[str], None]


@dataclass
class SttHypothesis:
    """One backend transcription candidate."""

    text: str
    engine: str
    confidence: float
    language: str = "en"
    avg_logprob: float | None = None
    language_probability: float | None = None
    partial: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class SttEngineCapabilities:
    streaming: bool = False
    offline: bool = True
    multilingual: bool = True
    gpu: bool = False


class STTEngine(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this engine can run on this machine."""

    @abstractmethod
    def capabilities(self) -> SttEngineCapabilities:
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        pass

    def availability_reason(self) -> str:
        if self.is_available():
            return "available"
        return "not configured or dependency missing"


def logprob_to_confidence(avg_logprob: float | None) -> float:
    """Map Whisper avg_logprob to 0..1 confidence."""
    if avg_logprob is None:
        return 0.55
    # typical good: -0.3 .. -0.6; poor: < -1.0
    import math

    return max(0.05, min(0.99, 1.0 / (1.0 + math.exp(-(avg_logprob + 0.65) * 4.0))))
