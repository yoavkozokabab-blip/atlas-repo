"""Noise suppression and echo cancellation before STT."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from config import STT_ECHO_CANCELLATION_ENABLED, STT_NOISE_SUPPRESSION_ENABLED
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stt.enhance")


def suppress_noise(audio: np.ndarray, *, strength: float = 0.35) -> np.ndarray:
    """Spectral gating — attenuate low-energy frames."""
    if audio.size < 256:
        return audio
    x = np.squeeze(audio).astype(np.float32, copy=True)
    frame = 512
    hop = 256
    out = np.zeros_like(x)
    window = np.hanning(frame)
    noise_floor = float(np.percentile(np.abs(x), 15)) + 1e-8
    for i in range(0, max(1, len(x) - frame), hop):
        chunk = x[i : i + frame]
        if len(chunk) < frame:
            chunk = np.pad(chunk, (0, frame - len(chunk)))
        spec = np.fft.rfft(chunk * window)
        mag = np.abs(spec)
        mask = np.clip((mag - noise_floor * (1.0 + strength)) / (mag + 1e-8), 0.0, 1.0)
        cleaned = np.fft.irfft(spec * mask, n=frame)
        out[i : i + frame] += cleaned[: min(frame, len(out) - i)]
    peak = float(np.max(np.abs(out))) or 1.0
    return np.clip(out / peak * 0.95, -1.0, 1.0)


def cancel_echo(audio: np.ndarray, *, delay_ms: int = 80, attenuation: float = 0.35) -> np.ndarray:
    """Subtract attenuated delayed copy (speaker bleed during TTS)."""
    x = np.squeeze(audio).astype(np.float32, copy=True)
    sr = 16000
    delay = int(sr * delay_ms / 1000.0)
    if delay <= 0 or len(x) <= delay:
        return x
    echo = np.zeros_like(x)
    echo[delay:] = x[:-delay] * attenuation
    y = x - echo
    peak = float(np.max(np.abs(y))) or 1.0
    return np.clip(y / peak * 0.95, -1.0, 1.0)


def enhance_audio_array(audio: np.ndarray) -> np.ndarray:
    x = audio
    if STT_NOISE_SUPPRESSION_ENABLED:
        x = suppress_noise(x)
    if STT_ECHO_CANCELLATION_ENABLED:
        x = cancel_echo(x)
    return x


def enhance_audio_file(path: Path) -> Path:
    """Write enhanced WAV alongside input; returns path to use for STT."""
    if not STT_NOISE_SUPPRESSION_ENABLED and not STT_ECHO_CANCELLATION_ENABLED:
        return path
    try:
        from faster_whisper.audio import decode_audio
        import soundfile as sf
    except ImportError:
        return path

    try:
        audio = decode_audio(str(path))
        audio = np.squeeze(audio).astype(np.float32)
        enhanced = enhance_audio_array(audio)
        tmp = Path(tempfile.mkstemp(suffix="_enhanced.wav")[1])
        sf.write(str(tmp), enhanced, 16000)
        return tmp
    except Exception as exc:
        logger.debug("audio enhance skipped: %s", exc)
        return path


def cleanup_enhanced_copy(enhanced: Path, original: Path) -> None:
    if enhanced != original and enhanced.is_file():
        try:
            enhanced.unlink(missing_ok=True)
        except OSError:
            pass
