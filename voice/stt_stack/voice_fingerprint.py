"""Voice fingerprint adaptation — bias grammar threshold per user."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from config import STT_STACK_PATH, STT_VOICE_FINGERPRINT_ENABLED, VOICE_GRAMMAR_MIN_SCORE
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stt.fingerprint")


@dataclass
class VoiceFingerprint:
    sample_count: int = 0
    spectral_centroid_mean: float = 0.0
    grammar_min_score: int = VOICE_GRAMMAR_MIN_SCORE


def _load() -> dict:
    path = Path(STT_STACK_PATH)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    path = Path(STT_STACK_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("stt_stack save failed: %s", exc)


def load_fingerprint() -> VoiceFingerprint:
    raw = _load().get("fingerprint") or {}
    return VoiceFingerprint(
        sample_count=int(raw.get("sample_count", 0)),
        spectral_centroid_mean=float(raw.get("spectral_centroid_mean", 0.0)),
        grammar_min_score=int(raw.get("grammar_min_score", VOICE_GRAMMAR_MIN_SCORE)),
    )


def save_fingerprint(fp: VoiceFingerprint) -> None:
    data = _load()
    data["fingerprint"] = {
        "sample_count": fp.sample_count,
        "spectral_centroid_mean": fp.spectral_centroid_mean,
        "grammar_min_score": fp.grammar_min_score,
    }
    _save(data)


def extract_spectral_centroid(audio: np.ndarray, sr: int = 16000) -> float:
    x = np.squeeze(audio).astype(np.float32)
    if x.size < 256:
        return 0.0
    spec = np.abs(np.fft.rfft(x[: min(len(x), sr)]))
    freqs = np.fft.rfftfreq(min(len(x), sr), 1.0 / sr)
    if spec.sum() < 1e-8:
        return 0.0
    return float(np.sum(freqs * spec) / np.sum(spec))


def adapt_from_audio(audio: np.ndarray) -> VoiceFingerprint:
    """Update fingerprint from calibration / successful wake samples."""
    if not STT_VOICE_FINGERPRINT_ENABLED:
        return load_fingerprint()
    fp = load_fingerprint()
    centroid = extract_spectral_centroid(audio)
    n = fp.sample_count
    fp.spectral_centroid_mean = (fp.spectral_centroid_mean * n + centroid) / (n + 1)
    fp.sample_count = n + 1
    if fp.sample_count >= 3:
        fp.grammar_min_score = max(78, VOICE_GRAMMAR_MIN_SCORE - 4)
    save_fingerprint(fp)
    return fp


def grammar_min_score_for_user() -> int:
    if not STT_VOICE_FINGERPRINT_ENABLED:
        return VOICE_GRAMMAR_MIN_SCORE
    return load_fingerprint().grammar_min_score


def reset_stt_stack_file() -> None:
    path = Path(STT_STACK_PATH)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
