"""NVIDIA Parakeet / NeMo ASR backend (optional)."""

from __future__ import annotations

from pathlib import Path

from config import PARAKEET_MODEL_PATH
from voice.stt_engines.base import (
    PartialCallback,
    STTEngine,
    SttEngineCapabilities,
    SttHypothesis,
)


class ParakeetEngine(STTEngine):
    name = "parakeet"

    def is_available(self) -> bool:
        if not PARAKEET_MODEL_PATH:
            return False
        path = Path(PARAKEET_MODEL_PATH)
        return path.is_file() or path.is_dir()

    def capabilities(self) -> SttEngineCapabilities:
        return SttEngineCapabilities(streaming=True, offline=True, gpu=True)

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        del on_partial, language
        try:
            import nemo.collections.asr as nemo_asr  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Parakeet requires nemo-toolkit. Set PARAKEET_MODEL_PATH or disable engine."
            ) from exc

        model = nemo_asr.models.ASRModel.restore_from(PARAKEET_MODEL_PATH)
        text = model.transcribe([str(audio_path)])[0]
        if hasattr(text, "text"):
            text = text.text
        return SttHypothesis(
            text=str(text).strip(),
            engine=self.name,
            confidence=0.85,
            language="en",
            metadata={"model": PARAKEET_MODEL_PATH},
        )
