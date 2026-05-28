"""Coqui XTTS-v2 optional engine (local model path)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

from voice.engines.base import EngineCapabilities, SynthesisChunk, TTSEngine, VoiceInfo


class XTTSEngine(TTSEngine):
    name = "xtts_v2"

    def _model_path(self) -> str:
        return os.getenv("XTTS_MODEL_PATH", "").strip()

    def is_available(self) -> bool:
        path = self._model_path()
        if not path:
            return False
        try:
            from TTS.api import TTS  # noqa: F401

            return Path(path).exists() or True
        except ImportError:
            return False

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming=False, neural=True, offline=True)

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        return [VoiceInfo(self.name, "default", "XTTS-v2 default speaker")]

    def synthesize_file(self, text: str, *, voice: str, rate_raw: str, out_path: Path) -> None:
        from TTS.api import TTS

        model = self._model_path() or "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model)
        fd, wav = tempfile.mkstemp(suffix=".wav", prefix="jarvis_xtts_")
        os.close(fd)
        path = Path(wav)
        try:
            tts.tts_to_file(text=text, file_path=str(path))
            from voice.streaming_player import play_wav_file

            play_wav_file(path)
        finally:
            path.unlink(missing_ok=True)

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        rate_raw: str,
    ) -> Iterator[SynthesisChunk]:
        self.synthesize_file(text, voice=voice, rate_raw=rate_raw, out_path=Path("_x"))
        yield SynthesisChunk(data=b"", mime="audio/wav", viseme_hint=0.5)
