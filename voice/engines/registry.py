"""Engine registry and fallback chain."""

from __future__ import annotations

from typing import Iterator

from voice.engines.base import SynthesisChunk, TTSEngine, VoiceInfo
from voice.engines.edge_engine import EdgeTTSEngine
from voice.engines.piper_engine import PiperEngine
from voice.engines.pyttsx3_engine import Pyttsx3Engine
from voice.engines.styletts2_engine import StyleTTS2Engine
from voice.engines.xtts_engine import XTTSEngine

_ENGINES: dict[str, TTSEngine] = {
    "edge_tts": EdgeTTSEngine(),
    "pyttsx3": Pyttsx3Engine(),
    "piper": PiperEngine(),
    "xtts_v2": XTTSEngine(),
    "styletts2": StyleTTS2Engine(),
}

_DEFAULT_CHAIN = ("edge_tts", "piper", "xtts_v2", "styletts2", "pyttsx3")


def list_registered_engines() -> list[str]:
    return list(_ENGINES.keys())


def get_engine(name: str) -> TTSEngine | None:
    key = (name or "").strip().lower().replace("-", "_")
    return _ENGINES.get(key)


def get_engine_chain(preferred: str | None = None) -> list[TTSEngine]:
    order: list[str] = []
    if preferred:
        order.append(preferred.strip().lower().replace("-", "_"))
    for name in _DEFAULT_CHAIN:
        if name not in order:
            order.append(name)
    engines: list[TTSEngine] = []
    for name in order:
        eng = get_engine(name)
        if eng is not None:
            engines.append(eng)
    return engines


def list_all_voices() -> list[VoiceInfo]:
    voices: list[VoiceInfo] = []
    seen: set[str] = set()
    for eng in _ENGINES.values():
        for v in eng.list_voices():
            key = f"{v.engine}:{v.voice_id}"
            if key in seen:
                continue
            seen.add(key)
            voices.append(v)
    return voices


def synthesize_with_fallback(
    text: str,
    *,
    preferred_engine: str,
    voice: str,
    rate_raw: str,
    allow_streaming: bool = True,
) -> tuple[str, Iterator[SynthesisChunk] | None]:
    """
    Returns (provider_name, chunk_iterator or None).
    If streaming supported and enabled, returns iterator; else plays via blocking path.
    """
    last_error: Exception | None = None
    for eng in get_engine_chain(preferred_engine):
        if not eng.is_available():
            continue
        caps = eng.capabilities()
        try:
            if allow_streaming and caps.streaming:
                chunks = eng.synthesize_stream(text, voice=voice, rate_raw=rate_raw)
                return eng.name, chunks
            if eng.name == "edge_tts":
                from voice.tts_edge import speak_edge_tts

                speak_edge_tts(text, voice=voice, rate_raw=rate_raw)
                return eng.name, None
            if eng.name == "pyttsx3":
                from voice.tts_pyttsx3 import speak_pyttsx3

                speak_pyttsx3(text, rate_raw=rate_raw)
                return eng.name, None
            from pathlib import Path
            import tempfile
            import os

            fd, tmp = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            path = Path(tmp)
            try:
                eng.synthesize_file(text, voice=voice, rate_raw=rate_raw, out_path=path)
            finally:
                path.unlink(missing_ok=True)
            return eng.name, None
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No TTS engine available")
