"""Phase 57 — low-latency streaming conversational TTS runtime."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterator
from typing import Callable

from core.logger import setup_logger
from voice.providers.base import SpeechProsody
from voice.providers.registry import get_provider_health, select_provider, speak_with_failover
from voice.streaming_player import (
    clear_stop_request,
    is_stop_requested,
    is_speaking,
    request_stop_speaking,
    stream_mp3_chunks_incremental,
)
from voice.voice_latency_metrics import (
    RealtimeVoiceLatency,
    begin_realtime_latency,
    format_voice_latency_status,
    record_realtime_latency,
)

logger = setup_logger("jarvis.voice.realtime_tts")

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+|\n+")
_active_lock = threading.Lock()
_active_cancel: Callable[[], None] | None = None


def is_realtime_tts_enabled() -> bool:
    try:
        import config as cfg
        from voice.tts_playback_trace import is_tts_safe_mode

        if is_tts_safe_mode() or getattr(cfg, "VOICE_RUNTIME_STABLE", False):
            return False
        if getattr(cfg, "PYTTSX3_FALLBACK_ONLY", True):
            return bool(getattr(cfg, "REALTIME_TTS_ENABLED", True))
        return bool(getattr(cfg, "REALTIME_TTS_ENABLED", True))
    except Exception:
        return False


def pyttsx3_fallback_only() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "PYTTSX3_FALLBACK_ONLY", True))
    except Exception:
        return True


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_RE.split(text or "") if p.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


def apply_prosody(text: str, *, emotion: str = "neutral", speed: float = 1.0) -> SpeechProsody:
    breath = emotion in {"thoughtful", "calm", "concerned"}
    pause_before = 80 if emotion == "thoughtful" else 0
    pause_after = 120 if breath else 40
    return SpeechProsody(
        emotion=emotion,
        speed=max(0.7, min(1.35, speed)),
        pause_before_ms=pause_before,
        pause_after_ms=pause_after,
        breath_pause=breath,
    )


def _register_active_cancel(cancel_fn: Callable[[], None] | None) -> None:
    global _active_cancel
    with _active_lock:
        _active_cancel = cancel_fn


def cancel_active_speech() -> bool:
    """Instant cancel — flush queued audio and stop playback (idempotent)."""
    global _active_cancel
    try:
        from voice.voice_latency_metrics import get_last_realtime_latency

        rec = get_last_realtime_latency()
        if rec is not None:
            rec.mark_interrupt_begin()
    except Exception:
        pass
    cancel_fn: Callable[[], None] | None = None
    with _active_lock:
        cancel_fn = _active_cancel
        _active_cancel = None
    cancelled = False
    if cancel_fn is not None:
        try:
            cancel_fn()
            cancelled = True
        except Exception:
            pass
    request_stop_speaking()
    try:
        from voice.voice_latency_metrics import get_last_realtime_latency

        rec = get_last_realtime_latency()
        if rec is not None:
            rec.mark_interrupt()
    except Exception:
        pass
    return cancelled or is_speaking()


def _play_provider_stream(
    provider_name: str,
    chunks,
    *,
    latency: RealtimeVoiceLatency,
    on_first_audio: Callable[[], None] | None = None,
) -> bool:
    if provider_name == "pyttsx3_fallback":
        for chunk in chunks:
            if is_stop_requested():
                break
            if chunk.data:
                latency.mark_first_audio()
                if on_first_audio:
                    on_first_audio()
        return not is_stop_requested()

    chunk_iter = iter(chunks)
    try:
        first_chunk = next(chunk_iter)
    except StopIteration:
        return True

    mime = first_chunk.mime or "audio/mpeg"
    if mime == "audio/wav":
        collected = [first_chunk.data] if first_chunk.data else []
        for chunk in chunk_iter:
            if is_stop_requested():
                break
            if chunk.data:
                collected.append(chunk.data)
                mime = chunk.mime or mime
        if not collected or is_stop_requested():
            return not is_stop_requested()

        import os
        import tempfile
        from pathlib import Path

        from voice.streaming_player import play_wav_file

        fd, path_str = tempfile.mkstemp(suffix=".wav", prefix="jarvis_rt_wav_")
        os.close(fd)
        path = Path(path_str)
        try:
            path.write_bytes(b"".join(collected))
            if collected:
                latency.mark_first_audio()
                if on_first_audio:
                    on_first_audio()
            return play_wav_file(path)
        finally:
            path.unlink(missing_ok=True)

    def _combined():
        if first_chunk.data and not is_stop_requested():
            yield first_chunk
        for chunk in chunk_iter:
            if is_stop_requested():
                break
            if chunk.data:
                yield chunk

    def _mark_first_playback() -> None:
        latency.mark_first_audio()
        if on_first_audio:
            on_first_audio()

    ok = stream_mp3_chunks_incremental(
        _combined(),
        on_first_playback=_mark_first_playback,
        on_first_byte=latency.mark_first_byte,
        on_first_decodable=latency.mark_first_decodable,
        on_adaptive_target=lambda size: setattr(latency, "adaptive_buffer_bytes", size),
    )
    return ok and not is_stop_requested()


def speak_realtime(
    text: str,
    *,
    voice: str = "",
    rate_raw: str = "",
    emotion: str = "neutral",
    preferred_provider: str = "",
) -> str:
    """
    Speak text with sentence-chunk streaming and provider failover.
    Returns provider name used.
    """
    from voice.tts import sanitize_for_speech

    safe = sanitize_for_speech(text)
    if not safe:
        return ""

    from voice.interruption_manager import on_jarvis_speech_finished, on_jarvis_speech_started

    clear_stop_request()
    on_jarvis_speech_started(safe)
    try:
        from voice.tts_output_policy import evaluate_tts_output, log_tts_output_decision, notify_overlay_speaking

        decision = evaluate_tts_output(
            voice_path="speak_realtime",
            input_mode="voice",
        )
        log_tts_output_decision(decision)
        try:
            from voice.tts_policy_trace import log_tts_policy_context

            log_tts_policy_context(
                stage="speak_realtime.after_policy",
                voice_path="speak_realtime",
                input_mode="voice",
                decision=decision,
            )
        except Exception:
            pass
        if not decision.allowed:
            on_jarvis_speech_finished(interrupted=False)
            return ""
        notify_overlay_speaking(streaming=True)
    except Exception:
        pass
    provider_used = ""
    latency = begin_realtime_latency(provider=preferred_provider or "auto", text=safe)
    t0 = time.perf_counter()
    try:
        sentences = split_sentences(safe)
        prosody = apply_prosody(safe, emotion=emotion)
        for idx, sentence in enumerate(sentences):
            if is_stop_requested():
                latency.cancelled = True
                break
            if idx and prosody.pause_before_ms:
                time.sleep(prosody.pause_before_ms / 1000.0)
            provider_name, chunks, provider = speak_with_failover(
                sentence,
                voice=voice,
                rate_raw=rate_raw,
                prosody=prosody,
                preferred=preferred_provider if idx == 0 else "",
            )
            provider_used = provider_name
            latency.provider = provider_name
            connect_ms = getattr(provider, "last_provider_connect_ms", lambda: None)()
            if connect_ms is None and provider_name == "elevenlabs":
                try:
                    from voice.providers.elevenlabs_websocket import get_elevenlabs_ws_session

                    connect_ms = get_elevenlabs_ws_session().last_connect_ms
                except Exception:
                    pass
            if connect_ms is not None:
                latency.provider_connect_ms = connect_ms

            def _cancel_current() -> None:
                request_stop_speaking()
                try:
                    provider.cancel()
                except Exception:
                    pass

            _register_active_cancel(_cancel_current)
            try:
                first_ms = getattr(provider, "last_time_to_first_audio_ms", lambda: None)()
                if first_ms is not None:
                    latency.provider_latency_ms = first_ms
                    if latency.first_byte_ms is None:
                        latency.first_byte_ms = first_ms
                ok = _play_provider_stream(
                    provider_name,
                    chunks,
                    latency=latency,
                )
            finally:
                _register_active_cancel(None)
            if not ok:
                latency.cancelled = is_stop_requested()
                break
            if prosody.pause_after_ms:
                time.sleep(prosody.pause_after_ms / 1000.0)
        latency.queue_wait_ms = max(0.0, (time.perf_counter() - t0) * 1000.0 - (latency.time_to_first_audio_ms or 0.0))
        latency.finish(cancelled=is_stop_requested())
        record_realtime_latency(latency)
        if provider_used and provider_used != "none":
            try:
                from voice.tts_output_policy import log_speech_synthesis_started

                log_speech_synthesis_started(voice_path="speak_realtime", provider=provider_used)
            except Exception:
                pass
        return provider_used or "none"
    except Exception as exc:
        latency.finish(cancelled=True)
        record_realtime_latency(latency)
        logger.warning("realtime TTS failed: %s", exc)
        raise
    finally:
        on_jarvis_speech_finished(interrupted=is_stop_requested())


def speak_realtime_parallel(
    text_chunks: Iterator[str],
    *,
    voice: str = "",
    rate_raw: str = "",
    emotion: str = "neutral",
) -> str:
    """Start speaking while text is still being generated (Phase 58 preemptive path)."""
    from voice.preemptive_tts import speak_preemptive_stream

    return speak_preemptive_stream(
        text_chunks,
        voice=voice,
        rate_raw=rate_raw,
        emotion=emotion,
    )


def show_realtime_tts_status() -> str:
    from voice.providers.provider_health import show_realtime_provider_status

    health = get_provider_health()
    selected = select_provider()
    lines = [
        "Realtime TTS runtime (Phase 57):",
        f"  enabled: {'yes' if is_realtime_tts_enabled() else 'no'}",
        f"  pyttsx3 fallback only: {'yes' if pyttsx3_fallback_only() else 'no'}",
        f"  selected provider: {selected.name if selected else 'none'}",
        "  providers:",
    ]
    for item in health:
        lines.append(
            f"    - {item.name}: {'available' if item.available else 'unavailable'} "
            f"fallback_only={item.fallback_only} ({item.reason})"
        )
    lines.append("")
    lines.append(format_voice_latency_status())
    lines.append("")
    lines.append(show_realtime_provider_status())
    return "\n".join(lines)


def phase57_status() -> str:
    from voice.backend_manager import show_backend_status

    return "\n\n".join([show_realtime_tts_status(), show_backend_status()])


def register_active_cancel_for_tests(cancel_fn: Callable[[], None] | None) -> None:
    """Test hook — simulate active provider stream during barge-in."""
    _register_active_cancel(cancel_fn)


def reset_realtime_tts_for_tests() -> None:
    global _active_cancel
    with _active_lock:
        _active_cancel = None
    request_stop_speaking()
    clear_stop_request()
    from voice.voice_latency_metrics import reset_realtime_latency_for_tests

    reset_realtime_latency_for_tests()
