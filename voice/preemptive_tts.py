"""Preemptive speculative TTS during LLM token streaming (Phase 58)."""

from __future__ import annotations

import threading
from collections.abc import Iterator

from core.logger import setup_logger
from voice.realtime_tts import cancel_active_speech, is_realtime_tts_enabled, speak_realtime, split_sentences

logger = setup_logger("jarvis.voice.preemptive_tts")

_lock = threading.Lock()
_active_generation = 0


def speak_preemptive_stream(
    text_chunks: Iterator[str],
    *,
    voice: str = "",
    rate_raw: str = "",
    emotion: str = "neutral",
) -> str:
    """
    Start TTS on completed sentences while text is still generating.
    Cancels and restarts mid-stream when superseded.
    """
    global _active_generation
    if not is_realtime_tts_enabled():
        combined = " ".join(c.strip() for c in text_chunks if c and c.strip())
        return speak_realtime(combined, voice=voice, rate_raw=rate_raw, emotion=emotion) if combined else ""

    with _lock:
        _active_generation += 1
        generation = _active_generation

    buffer = ""
    provider_used = ""
    for piece in text_chunks:
        with _lock:
            if generation != _active_generation:
                break
        if not piece or not piece.strip():
            continue
        buffer = f"{buffer} {piece}".strip()
        sentences = split_sentences(buffer)
        if len(sentences) <= 1:
            continue
        speakable = " ".join(sentences[:-1])
        buffer = sentences[-1]
        cancel_active_speech()
        provider_used = speak_realtime(
            speakable,
            voice=voice,
            rate_raw=rate_raw,
            emotion=emotion,
        ) or provider_used

    with _lock:
        if generation == _active_generation and buffer.strip():
            provider_used = speak_realtime(
                buffer.strip(),
                voice=voice,
                rate_raw=rate_raw,
                emotion=emotion,
            ) or provider_used
    return provider_used


def cancel_preemptive_synthesis() -> None:
    global _active_generation
    with _lock:
        _active_generation += 1
    cancel_active_speech()


def reset_preemptive_tts_for_tests() -> None:
    global _active_generation
    with _lock:
        _active_generation = 0
