"""STT engine registry and fallback chain (Phase 42)."""

from __future__ import annotations

from config import STT_ENGINE, STT_ENGINE_CHAIN
from voice.stt_engines.base import STTEngine
from voice.stt_engines.deepgram_local_engine import DeepgramLocalEngine
from voice.stt_engines.faster_whisper_engine import FasterWhisperEngine
from voice.stt_engines.onnx_whisper_engine import OnnxWhisperEngine
from voice.stt_engines.parakeet_engine import ParakeetEngine
from voice.stt_engines.whisper_cpp_engine import WhisperCppEngine

_ENGINES: dict[str, STTEngine] = {
    "faster_whisper": FasterWhisperEngine(),
    "whisper_cpp": WhisperCppEngine(),
    "onnx_whisper": OnnxWhisperEngine(),
    "parakeet": ParakeetEngine(),
    "deepgram_local": DeepgramLocalEngine(),
}

_DEFAULT_CHAIN = (
    "faster_whisper",
    "onnx_whisper",
    "whisper_cpp",
    "parakeet",
    "deepgram_local",
)


def list_registered_stt_engines() -> list[str]:
    return list(_ENGINES.keys())


def get_stt_engine(name: str) -> STTEngine | None:
    key = (name or "").strip().lower().replace("-", "_")
    aliases = {
        "whisper": "faster_whisper",
        "faster-whisper": "faster_whisper",
        "onnx": "onnx_whisper",
        "directml": "onnx_whisper",
        "deepgram": "deepgram_local",
    }
    key = aliases.get(key, key)
    return _ENGINES.get(key)


def _parse_chain() -> list[str]:
    raw = (STT_ENGINE_CHAIN or "").strip()
    if raw:
        return [p.strip().lower().replace("-", "_") for p in raw.split(",") if p.strip()]
    preferred = (STT_ENGINE or "faster_whisper").strip().lower().replace("-", "_")
    if preferred in {"whisper", "faster-whisper"}:
        preferred = "faster_whisper"
    order = [preferred]
    for name in _DEFAULT_CHAIN:
        if name not in order:
            order.append(name)
    return order


def get_stt_engine_chain() -> list[STTEngine]:
    engines: list[STTEngine] = []
    seen: set[str] = set()
    for name in _parse_chain():
        if name in seen:
            continue
        seen.add(name)
        eng = get_stt_engine(name)
        if eng is not None:
            engines.append(eng)
    return engines


def list_available_stt_engines() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, eng in _ENGINES.items():
        status = eng.availability_reason() if eng.is_available() else eng.availability_reason()
        out.append((name, status))
    return out
