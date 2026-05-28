"""Optional ONNX DirectML STT (AMD/Intel GPU via onnx-asr + onnxruntime-directml)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import DATA_DIR
from voice.stt_acceleration import get_onnx_providers, probe_acceleration
from voice.stt_config import normalize_stt_model

logger = logging.getLogger("jarvis.voice.stt.directml")

_model_cache: Any | None = None
_loaded_label: str | None = None
_loaded_provider: str | None = None


class DirectMLSttError(Exception):
    """DirectML / onnx-asr STT failed or is not available."""


def onnx_asr_model_id(stt_model: str) -> str:
    """Map JARVIS STT_MODEL name to onnx-asr Hugging Face model id."""
    key = normalize_stt_model(stt_model)
    mapping = {
        "tiny": "onnx-community/whisper-tiny",
        "base": "onnx-community/whisper-base",
        "small": "onnx-community/whisper-small",
        "medium": "onnx-community/whisper-small",
        "large": "onnx-community/whisper-large-v3-turbo",
        "large-v2": "onnx-community/whisper-large-v3-turbo",
        "large-v3": "onnx-community/whisper-large-v3-turbo",
        "distil-large-v3": "onnx-community/whisper-large-v3-turbo",
    }
    return mapping.get(key, "onnx-community/whisper-small")


def local_onnx_model_dir(stt_model: str) -> Path:
    """Optional offline model directory under data/models/whisper_onnx/."""
    custom = (Path(__file__).resolve().parent.parent / "data" / "models" / "whisper_onnx" / normalize_stt_model(stt_model))
    if custom.is_dir():
        return custom
    return DATA_DIR / "models" / "whisper_onnx" / normalize_stt_model(stt_model)


def directml_diagnostics() -> dict[str, object]:
    probe = probe_acceleration()
    providers = get_onnx_providers(prefer_directml=True)
    chosen = providers[0] if providers else "CPUExecutionProvider"
    return {
        "directml_available": probe.directml_available,
        "directml_reason": probe.directml_reason,
        "onnx_providers": list(probe.onnx_providers),
        "chosen_providers": providers,
        "chosen_provider": chosen,
        "onnx_asr_installed": _onnx_asr_available(),
    }


def is_directml_available() -> bool:
    """True when DirectML ONNX provider is probed and available."""
    try:
        probe = probe_acceleration()
        return bool(probe.directml_available)
    except Exception:
        return False


def _onnx_asr_available() -> bool:
    try:
        import onnx_asr  # noqa: F401

        return True
    except ImportError:
        return False


def reset_directml_model_cache() -> None:
    global _model_cache, _loaded_label, _loaded_provider
    _model_cache = None
    _loaded_label = None
    _loaded_provider = None


def load_onnx_asr_model(*, stt_model: str, prefer_directml: bool = True) -> Any:
    """Load onnx-asr Whisper model with DirectML when available."""
    global _model_cache, _loaded_label, _loaded_provider
    if _model_cache is not None:
        return _model_cache

    if not _onnx_asr_available():
        raise DirectMLSttError(
            "onnx-asr is not installed. For AMD GPU STT: "
            "pip install onnxruntime-directml onnx-asr[cpu,hub]"
        )

    probe = probe_acceleration()
    if prefer_directml and not probe.directml_available:
        raise DirectMLSttError(probe.directml_reason)

    import onnx_asr

    providers = get_onnx_providers(prefer_directml=prefer_directml)
    model_id = onnx_asr_model_id(stt_model)
    local_dir = local_onnx_model_dir(stt_model)

    try:
        if local_dir.is_dir():
            _model_cache = onnx_asr.load_model(model_id, str(local_dir), providers=providers)
            source = f"local:{local_dir}"
        else:
            _model_cache = onnx_asr.load_model(model_id, providers=providers)
            source = model_id
    except Exception as exc:
        raise DirectMLSttError(f"Failed to load onnx-asr model {model_id}: {exc}") from exc

    _loaded_provider = providers[0] if providers else "CPUExecutionProvider"
    _loaded_label = f"onnx-asr/{source} [{_loaded_provider}]"
    logger.info("Loaded DirectML STT model: %s", _loaded_label)
    print(f"STT model loaded: {_loaded_label}", flush=True)
    return _model_cache


def transcribe_onnx_directml(
    audio_path: Path,
    *,
    stt_model: str,
    language: str,
    prefer_directml: bool = True,
) -> tuple[str, str, str]:
    """
    Transcribe WAV via onnx-asr. Returns (text, provider, loaded_label).
  """
    model = load_onnx_asr_model(stt_model=stt_model, prefer_directml=prefer_directml)
    try:
        text = model.recognize(str(audio_path))
    except Exception as exc:
        raise DirectMLSttError(f"DirectML transcription failed: {exc}") from exc
    if not isinstance(text, str):
        text = str(text)
    return text.strip(), _loaded_provider or "unknown", _loaded_label or "onnx-asr"
