"""faster-whisper STT backend."""

from __future__ import annotations

from pathlib import Path

from voice.stt_engines.base import (
    PartialCallback,
    STTEngine,
    SttEngineCapabilities,
    SttHypothesis,
    logprob_to_confidence,
)


class FasterWhisperEngine(STTEngine):
    name = "faster_whisper"

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def capabilities(self) -> SttEngineCapabilities:
        from voice.stt_acceleration import get_stt_runtime

        runtime = get_stt_runtime()
        return SttEngineCapabilities(
            streaming=True,
            offline=True,
            multilingual=True,
            gpu=runtime.whisper_device == "cuda",
        )

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        from voice.transcriber import transcribe_faster_whisper_hypothesis

        return transcribe_faster_whisper_hypothesis(
            audio_path, language=language, on_partial=on_partial
        )
