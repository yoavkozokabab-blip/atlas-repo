"""StyleTTS2 optional engine (external script hook)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

from voice.engines.base import EngineCapabilities, SynthesisChunk, TTSEngine, VoiceInfo


class StyleTTS2Engine(TTSEngine):
    name = "styletts2"

    def _script(self) -> str:
        return os.getenv("STYLETTS2_SCRIPT", "").strip()

    def is_available(self) -> bool:
        script = self._script()
        return bool(script and Path(script).is_file())

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming=False, neural=True, offline=True)

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        return [VoiceInfo(self.name, "default", "StyleTTS2 configured script")]

    def synthesize_file(self, text: str, *, voice: str, rate_raw: str, out_path: Path) -> None:
        script = self._script()
        fd, wav = tempfile.mkstemp(suffix=".wav", prefix="jarvis_styletts2_")
        os.close(fd)
        path = Path(wav)
        try:
            subprocess.run(
                ["py", "-3", script, "--text", text, "--output", str(path)],
                check=True,
                timeout=120,
                capture_output=True,
            )
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
