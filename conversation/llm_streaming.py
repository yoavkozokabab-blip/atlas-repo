"""Incremental LLM response streaming for conversational runtime (Phase 59)."""

from __future__ import annotations

import re
import threading
from collections.abc import Iterator

from core.logger import setup_logger
from conversation.emotional_speech import SpeechStyle, infer_speech_style
from conversation.memory_runtime import build_llm_context_prompt
from voice.realtime_tts import split_sentences

logger = setup_logger("jarvis.conversation.llm_streaming")

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
_lock = threading.Lock()
_generation = 0


def _next_generation() -> int:
    global _generation
    with _lock:
        _generation += 1
        return _generation


def cancel_llm_stream() -> None:
    _next_generation()


def stream_sentence_fragments(
    user_text: str,
    *,
    system: str | None = None,
    context_prompt: str | None = None,
) -> Iterator[str]:
    """
    Stream LLM tokens and yield speakable sentence fragments as they complete.
    Falls back to chunked user echo when Ollama is unavailable.
    """
    generation = _next_generation()
    ctx = context_prompt or build_llm_context_prompt()
    style = infer_speech_style(text=user_text)
    system_prompt = system or (
        "You are JARVIS, a concise conversational assistant. "
        "Reply naturally in short spoken sentences. "
        f"Speaking style hint: {style.label}."
    )
    prompt = f"{ctx}\n\nUser: {user_text.strip()}\nAssistant:"
    buffer = ""
    first_token = False
    try:
        from conversation.conversation_metrics import get_last_conversation_metrics
        from integrations.ollama_client import OllamaClient, OllamaError

        client = OllamaClient()
        for token in client.stream_chat_tokens(prompt, system=system_prompt):
            with _lock:
                if generation != _generation:
                    return
            if not first_token:
                first_token = True
                rec = get_last_conversation_metrics()
                if rec is not None:
                    rec.mark_llm_first_token()
            buffer += token
            parts = split_sentences(buffer)
            if len(parts) <= 1:
                continue
            for sentence in parts[:-1]:
                yield sentence.strip()
            buffer = parts[-1]
        if buffer.strip():
            yield buffer.strip()
        return
    except Exception as exc:
        logger.debug("LLM stream fallback: %s", exc)

    if not first_token:
        try:
            from conversation.conversation_metrics import get_last_conversation_metrics

            rec = get_last_conversation_metrics()
            if rec is not None:
                rec.mark_llm_first_token()
        except Exception:
            pass
    fallback = f"I heard you say: {user_text.strip()[:180]}"
    for sentence in split_sentences(fallback):
        yield sentence


def stream_response_chunks(user_text: str, *, style: SpeechStyle | None = None) -> Iterator[str]:
    """Alias for preemptive TTS feeding with optional style metadata."""
    del style
    yield from stream_sentence_fragments(user_text)


def speak_streaming_response(
    user_text: str,
    *,
    intent: str = "conversational",
    input_mode: str = "voice",
) -> str:
    """Generate + speak a conversational response with preemptive TTS."""
    from conversation.conversation_metrics import begin_conversation_turn, record_conversation_turn
    from conversation.emotional_speech import infer_speech_style
    from conversation.memory_runtime import record_conversational_turn
    from voice.interruption_manager import on_jarvis_speech_finished, on_jarvis_speech_started
    from voice.streaming_pipeline import get_streaming_pipeline

    style = infer_speech_style(text=user_text, intent=intent)
    metrics = begin_conversation_turn()
    fragments = stream_sentence_fragments(user_text)
    spoken_parts: list[str] = []

    def _chunk_iter() -> Iterator[str]:
        for frag in fragments:
            spoken_parts.append(frag)
            yield frag

    on_jarvis_speech_started(user_text)
    provider = get_streaming_pipeline().speak_response_stream(
        _chunk_iter(),
        emotion=style.emotion,
    )
    full = " ".join(spoken_parts).strip()
    on_jarvis_speech_finished(interrupted=False)
    try:
        from conversation.conversation_metrics import get_last_conversation_metrics
        from voice.voice_latency_metrics import get_last_realtime_latency

        rec = get_last_conversation_metrics()
        rt = get_last_realtime_latency()
        if rec and rt and rt.time_to_first_audio_ms is not None:
            rec.mark_tts_first_audio()
    except Exception:
        pass
    record_conversational_turn(
        user_text=user_text,
        assistant_text=full,
        intent=intent,
        input_mode=input_mode,
        speech_style=style.label,
    )
    record_conversation_turn(metrics)
    return provider or "conversational_stream"
