"""pyttsx3 engine adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from voice.engines.base import EngineCapabilities, SynthesisChunk, TTSEngine, VoiceInfo


class Pyttsx3Engine(TTSEngine):
    name = "pyttsx3"

    def is_available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401

            return True
        except ImportError:
            return False

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming=False, neural=False, offline=True)

    def list_voices(self) -> list[VoiceInfo]:
        from voice.audio_devices import list_pyttsx3_voices

        return [
            VoiceInfo(self.name, name, name, language="en")
            for name in list_pyttsx3_voices()[:20]
        ]

    def synthesize_file(self, text: str, *, voice: str, rate_raw: str, out_path: Path) -> None:
        from voice.tts_pyttsx3 import speak_pyttsx3

        speak_pyttsx3(text, rate_raw=rate_raw)

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        rate_raw: str,
    ) -> Iterator[SynthesisChunk]:
        self.synthesize_file(text, voice=voice, rate_raw=rate_raw, out_path=Path("_unused"))
        yield SynthesisChunk(data=b"", mime="audio/wav", viseme_hint=0.5)
