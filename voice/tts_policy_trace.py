"""Structured TTS policy tracing for live wakeword / conversational debugging."""

from __future__ import annotations

import json
import threading
from typing import Any

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.tts_policy_trace")


def tts_policy_trace_enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "TTS_POLICY_TRACE", True))
    except Exception:
        return True


def collect_tts_policy_context(
    *,
    stage: str,
    speak_enabled: bool | None = None,
    voice_path: str = "",
    input_mode: str = "",
    intent: str = "",
    suppress_speech: bool | None = None,
    decision: object | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "stage": stage,
        "thread": threading.current_thread().name,
        "voice_path": voice_path or "",
        "input_mode": input_mode or "",
        "intent": intent or "",
    }
    if speak_enabled is not None:
        ctx["speak_enabled"] = speak_enabled
    if suppress_speech is not None:
        ctx["suppress_speech"] = suppress_speech

    try:
        import config as cfg

        ctx["TOOL_FIRST_MODE"] = bool(getattr(cfg, "TOOL_FIRST_MODE", False))
        ctx["HUMAN_CONVERSATIONAL_RUNTIME_ENABLED"] = bool(
            getattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False)
        )
        ctx["VOICE_RUNTIME_MODE"] = str(getattr(cfg, "VOICE_RUNTIME_MODE", "") or "")
        ctx["STT_STREAMING_BUFFER_ENABLED"] = bool(
            getattr(cfg, "STT_STREAMING_BUFFER_ENABLED", False)
        )
    except Exception as exc:
        ctx["config_error"] = str(exc)[:120]

    try:
        from conversation.human_runtime import (
            is_human_conversational_runtime_enabled,
            is_session_active,
            should_start_human_session_after_wake,
        )

        ctx["human_runtime_enabled"] = is_human_conversational_runtime_enabled()
        ctx["session_active"] = is_session_active()
        ctx["should_start_human_session_after_wake"] = should_start_human_session_after_wake(None)
    except Exception as exc:
        ctx["human_runtime_error"] = str(exc)[:120]

    try:
        from voice.continuous_mic import is_streaming_session_active

        ctx["streaming_mic_active"] = is_streaming_session_active()
    except Exception as exc:
        ctx["streaming_mic_error"] = str(exc)[:120]

    try:
        from voice.streaming_stt import is_streaming_stt_enabled

        ctx["streaming_stt_enabled"] = is_streaming_stt_enabled()
    except Exception as exc:
        ctx["streaming_stt_error"] = str(exc)[:120]

    try:
        from assistant.conversation_state import get_overlay_snapshot

        conv = get_overlay_snapshot()
        ctx["continuous_listening"] = bool(conv.get("continuous_listening"))
    except Exception as exc:
        ctx["conversation_state_error"] = str(exc)[:120]

    try:
        from voice.tts_output_policy import conversational_session_has_priority

        ctx["conversational_session_priority"] = conversational_session_has_priority()
    except Exception as exc:
        ctx["priority_error"] = str(exc)[:120]

    try:
        from voice.audio_status import get_audio_status

        audio = get_audio_status()
        ctx["selected_verified_audio_backend"] = audio.selected_verified_audio_backend or "none"
        ctx["active_tts_backend"] = audio.active_backend or "none"
    except Exception as exc:
        ctx["audio_status_error"] = str(exc)[:120]

    if decision is not None:
        ctx["policy_allowed"] = getattr(decision, "allowed", None)
        ctx["policy_reason"] = getattr(decision, "reason", None)
        ctx["policy_session_active"] = getattr(decision, "session_active", None)
        ctx["policy_overlay_status"] = getattr(decision, "overlay_status", None)
        ctx["policy_audio_mode"] = getattr(decision, "audio_mode", None)
        ctx["policy_tool_first_mode"] = getattr(decision, "tool_first_mode", None)
        ctx["policy_suppress_flags"] = getattr(decision, "suppress_flags", None)

    if extra:
        ctx.update(extra)
    return ctx


def log_tts_policy_context(**kwargs: Any) -> dict[str, Any]:
    ctx = collect_tts_policy_context(**kwargs)
    if tts_policy_trace_enabled():
        logger.info("TTS_POLICY_TRACE %s", json.dumps(ctx, default=str, sort_keys=True))
    return ctx
