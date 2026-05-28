"""ONNX Whisper (DirectML / CPU) backend."""

from __future__ import annotations

from pathlib import Path

from config import STT_MODEL, STT_PREFER_DIRECTML
from voice.stt_config import normalize_stt_model
from voice.stt_engines.base import (
    PartialCallback,
    STTEngine,
    SttEngineCapabilities,
    SttHypothesis,
)
from voice.transcriber import _evaluate_confidence


class OnnxWhisperEngine(STTEngine):
    name = "onnx_whisper"

    def is_available(self) -> bool:
        try:
            from voice.stt_directml import _onnx_asr_available

            return _onnx_asr_available()
        except Exception:
            return False

    def capabilities(self) -> SttEngineCapabilities:
        return SttEngineCapabilities(streaming=False, offline=True, multilingual=True)

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        del on_partial
        from voice.stt_directml import transcribe_onnx_directml

        model_name = normalize_stt_model(STT_MODEL)
        text, _provider, _label = transcribe_onnx_directml(
            audio_path,
            stt_model=model_name,
            language=language,
            prefer_directml=STT_PREFER_DIRECTML,
        )
        low, _rec = _evaluate_confidence(None, None, language)
        conf = 0.45 if low else 0.72
        return SttHypothesis(
            text=text.strip(),
            engine=self.name,
            confidence=conf,
            language=language,
            metadata={"provider": _provider},
        )
