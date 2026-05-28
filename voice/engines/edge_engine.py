"""edge-tts engine adapter."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Iterator

from voice.engines.base import EngineCapabilities, SynthesisChunk, TTSEngine, VoiceInfo
from voice.tts_config import resolve_edge_tts_rate


class EdgeTTSEngine(TTSEngine):
    name = "edge_tts"

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            return True
        except ImportError:
            return False

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(streaming=True, neural=True, offline=False)

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        try:
            import asyncio

            import edge_tts

            voices = asyncio.run(edge_tts.list_voices())
            out: list[VoiceInfo] = []
            for v in voices[:40]:
                if not str(v.get("Locale", "")).startswith("en"):
                    continue
                short = str(v.get("ShortName", ""))
                if not short:
                    continue
                gender = str(v.get("Gender", ""))
                out.append(
                    VoiceInfo(
                        engine=self.name,
                        voice_id=short,
                        label=f"{short} ({gender})",
                        language="en",
                        gender=gender.lower(),
                    )
                )
            return out
        except Exception:
            return [
                VoiceInfo(self.name, "en-US-JennyNeural", "Jenny (female neural)"),
                VoiceInfo(self.name, "en-US-AriaNeural", "Aria (female neural)"),
            ]

    def synthesize_file(self, text: str, *, voice: str, rate_raw: str, out_path: Path) -> None:
        import asyncio

        import edge_tts

        rate = resolve_edge_tts_rate(rate_raw)

        async def _save() -> None:
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            await communicate.save(str(out_path))

        asyncio.run(_save())

    def synthesize_stream(
        self,
        text: str,
        *,
        voice: str,
        rate_raw: str,
    ) -> Iterator[SynthesisChunk]:
        if not self.is_available():
            raise RuntimeError("edge-tts not installed")
        rate = resolve_edge_tts_rate(rate_raw)

        async def _stream() -> list[bytes]:
            import edge_tts

            chunks: list[bytes] = []
            communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    chunks.append(chunk["data"])
            return chunks

        parts = asyncio.run(_stream())
        for i, blob in enumerate(parts):
            if not blob:
                continue
            hint = 0.45 + 0.1 * (i % 3)
            yield SynthesisChunk(data=blob, mime="audio/mpeg", viseme_hint=hint)
