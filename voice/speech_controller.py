"""Phase 41 — unified speak/stop/barge-in orchestration."""

from __future__ import annotations

import time

import config as cfg
from core.logger import setup_logger
from voice.streaming_player import (
    clear_stop_request,
    is_stop_requested,
    is_speaking,
    request_stop_speaking,
    stream_mp3_chunks_incremental,
)
from voice.tts import sanitize_for_speech
from voice.tts_playback_trace import (
    is_tts_safe_mode,
    log_tts_debug,
    record_playback_failure,
)

logger = setup_logger("jarvis.voice.speech")


def stop_speaking() -> None:
    if is_tts_safe_mode():
        log_tts_debug("stop_ignored_safe_mode")
        return
    request_stop_speaking()


def barge_in_if_speaking() -> bool:
    """Interrupt TTS if active (wake word / new command)."""
    if is_tts_safe_mode():
        return False
    interrupted = False
    try:
        from voice.realtime_tts import cancel_active_speech

        interrupted = cancel_active_speech()
    except Exception:
        pass
    if is_speaking():
        request_stop_speaking()
        interrupted = True
    return interrupted


def _push_viseme(level: float) -> None:
    if is_tts_safe_mode():
        return
    try:
        from ui.overlay_app import notify_overlay_viseme

        notify_overlay_viseme(level)
    except Exception:
        pass


def _speak_safe_mode(text: str) -> str:
    from voice.audio_status import record_normal_speech_path
    from voice.audio_verified import block_unverified_speech_with_warning
    from voice.tts_backend import get_verified_normal_speech_backend, prefer_subprocess_pyttsx3

    if not block_unverified_speech_with_warning():
        return ""

    if prefer_subprocess_pyttsx3():
        from voice.tts_subprocess import speak_subprocess_pyttsx3

        provider = get_verified_normal_speech_backend() or "subprocess_pyttsx3"
        log_tts_debug("safe_mode_path", engine=provider)
        result = speak_subprocess_pyttsx3(text)
        if not result.ok:
            raise RuntimeError(
                (result.stderr or "").strip() or f"exit {result.exit_code}"
            )
        record_normal_speech_path(provider)
        return provider

    from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER

    log_tts_debug("safe_mode_path", engine="pyttsx3")
    NORMAL_DIRECT_SPEAKER(text, rate_raw=cfg.TTS_RATE_RAW, record_user_success=False)
    return "pyttsx3_safe"


def _speak_streaming(text: str, *, engine: str | None, voice: str | None) -> str:
    from voice.engines.registry import synthesize_with_fallback
    from voice.viseme_timeline import build_viseme_frames

    clear_stop_request()
    eng_name = engine or cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE
    voice_id = voice or cfg.TTS_VOICE
    rate = cfg.TTS_RATE_RAW
    allow_stream = getattr(cfg, "TTS_STREAMING_ENABLED", True)

    frames = build_viseme_frames(text, rate_raw=rate)
    frame_idx = 0

    def _viseme_tick() -> None:
        nonlocal frame_idx
        if frame_idx < len(frames):
            _push_viseme(frames[frame_idx])
            frame_idx += 1

    provider, chunks = synthesize_with_fallback(
        text,
        preferred_engine=eng_name,
        voice=voice_id,
        rate_raw=rate,
        allow_streaming=allow_stream,
    )
    log_tts_debug("engine_selected", provider=provider, streaming=chunks is not None)

    if chunks is not None:
        ok = stream_mp3_chunks_incremental(chunks, on_viseme=lambda h: _push_viseme(h))
        if not ok and not is_stop_requested():
            log_tts_debug("streaming_failed_no_pyttsx3_retry")
            try:
                from voice.realtime_tts import is_realtime_tts_enabled, speak_realtime

                if is_realtime_tts_enabled():
                    return speak_realtime(text) or provider
            except Exception as exc:
                record_playback_failure(exc, engine=provider, path="streaming_retry")
                raise
        return provider

    for _ in range(len(frames)):
        if is_stop_requested():
            break
        _viseme_tick()
        time.sleep(0.05)
    return provider


def speak_text(text: str, *, engine: str | None = None, voice: str | None = None) -> str:
    """
    Speak sanitized text with streaming when available.
    Returns provider name used.
    """
    safe = sanitize_for_speech(text)
    if not safe:
        return ""

    from voice.tts_backend import must_use_verified_backend_for_normal_speech

    if (
        is_tts_safe_mode()
        or getattr(cfg, "VOICE_RUNTIME_STABLE", False)
        or must_use_verified_backend_for_normal_speech()
    ):
        return _speak_safe_mode(safe)

    try:
        from voice.realtime_tts import is_realtime_tts_enabled, speak_realtime

        if is_realtime_tts_enabled():
            return speak_realtime(safe, voice=voice or cfg.TTS_VOICE, rate_raw=cfg.TTS_RATE_RAW)
    except Exception as exc:
        logger.warning("realtime TTS path failed, falling back: %s", exc)

    try:
        from core.event_bus import get_event_bus

        get_event_bus().publish_nowait("tts.stream.started", chars=len(safe))
    except Exception:
        pass

    try:
        return _speak_streaming(safe, engine=engine, voice=voice)
    finally:
        try:
            from core.event_bus import get_event_bus

            get_event_bus().publish_nowait(
                "tts.stream.finished",
                provider=engine or cfg.TTS_ENGINE,
                stopped=is_stop_requested(),
            )
        except Exception:
            pass
