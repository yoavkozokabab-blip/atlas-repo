"""Lightweight audio preprocessing before STT."""

from __future__ import annotations

import numpy as np


def normalize_audio_float(audio: np.ndarray) -> np.ndarray:
    """
    Peak + gentle RMS normalization for noisy mic input.
    Input/output: float32 mono, roughly -1..1.
    """
    if audio.size == 0:
        return audio
    try:
        from config import STT_STACK_ENABLED

        if STT_STACK_ENABLED:
            from voice.stt_stack.audio_enhance import enhance_audio_array

            audio = enhance_audio_array(np.squeeze(audio).astype(np.float32))
    except Exception:
        pass
    x = np.squeeze(audio).astype(np.float32, copy=False)
    if x.ndim > 1:
        x = x[:, 0]
    peak = float(np.max(np.abs(x)))
    if peak > 1e-6:
        x = x / peak * 0.95
    rms = float(np.sqrt(np.mean(x * x)))
    target_rms = 0.08
    if rms > 1e-6 and rms < target_rms:
        x = x * min(3.0, target_rms / rms)
    return np.clip(x, -1.0, 1.0)
