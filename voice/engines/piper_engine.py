"""Piper TTS engine (optional local neural)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

from voice.engines.base import EngineCapabilities, SynthesisChunk, TTSEngine, VoiceInfo


class PiperEngine(TTSEngine):
    name = "piper"

    def _bin(self) -> str:
        return os.getenv("PIPER_BIN", "piper").strip()

    def _model(self) -> str:
        return os.getenv("PIPER_MODEL", "").strip()

    def is_available(self) -> bool:
        model = self._model()
        if not model or not Path(model).is_file():
            return False
        try:
            proc = subprocess.run(
                [self._bin(), "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming=False, neural=True, offline=True)

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        return [VoiceInfo(self.name, self._model(), Path(self._model()).stem)]

    def synthesize_file(self, text: str, *, voice: str, rate_raw: str, out_path: Path) -> None:
        model = voice or self._model()
        fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_piper_")
        os.close(fd)
        path = Path(wav_path)
        try:
            proc = subprocess.run(
                [self._bin(), "--model", model, "--output_file", str(path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=60,
                check=True,
            )
            if proc.stderr:
                pass
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
