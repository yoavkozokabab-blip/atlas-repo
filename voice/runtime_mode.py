"""Voice runtime presets — stable baseline overrides advanced STT/TTS paths."""

from __future__ import annotations

import os
from typing import Any


def voice_runtime_mode() -> str:
    return (os.getenv("VOICE_RUNTIME_MODE", "") or "").strip().lower()


def is_stable_voice_mode() -> bool:
    return voice_runtime_mode() == "stable"


def is_realtime_experimental_mode() -> bool:
    return voice_runtime_mode() in {"realtime_experimental", "realtime"}


def apply_voice_runtime_mode() -> None:
    """Apply stable or realtime-experimental overrides after config.py loads env + voice profile."""
    import config as cfg

    cfg.VOICE_RUNTIME_MODE = voice_runtime_mode()
    cfg.VOICE_RUNTIME_STABLE = is_stable_voice_mode()
    if is_realtime_experimental_mode():
        _apply_realtime_experimental_overrides(cfg)
        return
    if not is_stable_voice_mode():
        return

    from voice.stt_config import normalize_stt_model

    overrides: dict[str, Any] = {
        "VOICE_ENABLED": True,
        "STT_STREAMING_BUFFER_ENABLED": False,
        "CONVERSATION_SEMANTIC_STREAM_ENABLED": False,
        "STT_MULTIPASS_ENABLED": False,
        "STT_STACK_ENABLED": False,
        "STT_RETRY_ON_UNKNOWN": False,
        "STT_PARTIAL_STREAMING_ENABLED": False,
        "STT_STREAM_PARTIAL_ACCURATE_RETRY_ENABLED": False,
        "STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED": False,
        "STT_DEVICE_REQUEST": "cpu",
        "STT_DEVICE": "cpu",
        "STT_ACCELERATION_AUTO": False,
        "STT_PREFER_DIRECTML": False,
        "STT_FAST_PROFILE": False,
        "FAST_VOICE_MODE": False,
        "STT_COMPUTE_TYPE": "int8",
        "_STT_MODEL_RAW": "small",
        "STT_MODEL": normalize_stt_model("small"),
        "STT_BEAM_SIZE": 2,
        "STT_MAX_RECORD_SECONDS": 5,
        "WAKE_MAX_LISTEN_SECONDS": 5.0,
        "WAKE_WORD_LISTEN_SECONDS_AFTER_WAKE": 5.0,
        "STT_TIMEOUT_SECONDS": 12.0,
        "STT_WAKE_FALLBACK_TIMEOUT_SECONDS": 12.0,
        "TTS_TIMEOUT_SECONDS": 8.0,
        "TTS_SPEAK_MAX_SECONDS": 8.0,
        "TTS_ENABLED": True,
        "TTS_ENGINE": "pyttsx3",
        "TTS_FORCE_ENGINE": "pyttsx3",
        "TTS_BACKEND": "subprocess_pyttsx3",
        "TTS_ASYNC": False,
        "TTS_STREAMING_ENABLED": False,
        "TTS_BARGE_IN_ENABLED": False,
        "TTS_SAFE_MODE": True,
        "REALTIME_TTS_ENABLED": False,
        "VOICE_COMMAND_GUARD_ENABLED": False,
        "WAKE_EARLY_STOP_ENABLED": False,
        "SEMANTIC_LLM_ENABLED": False,
        "VOICE_LATENCY_INSTANT": False,
    }
    for key, value in overrides.items():
        setattr(cfg, key, value)


def _apply_realtime_experimental_overrides(cfg: object) -> None:
    overrides: dict[str, Any] = {
        "VOICE_ENABLED": True,
        "REALTIME_TTS_ENABLED": True,
        "PYTTSX3_FALLBACK_ONLY": True,
        "TTS_PRIMARY_BACKEND": "realtime",
        "TTS_FALLBACK_BACKEND": "pyttsx3_direct",
        "TTS_SAFE_MODE": False,
        "TTS_STREAMING_ENABLED": True,
        "TTS_BARGE_IN_ENABLED": True,
        "VOICE_COMMAND_GUARD_ENABLED": True,
        "STT_STREAMING_BUFFER_ENABLED": True,
        "STT_PARTIAL_STREAMING_ENABLED": True,
        "CONVERSATION_SEMANTIC_STREAM_ENABLED": True,
        "CONV_INTERRUPTION_ENABLED": True,
        "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED": True,
        "CONVERSATION_CONTINUOUS_MIC_ENABLED": True,
        "CONVERSATION_PARTIAL_INTERVAL_MS": 150.0,
        "CONVERSATION_TURN_MAX_SECONDS": 45.0,
        "STT_PARTIAL_INTERVAL_MS": 150.0,
        "FAST_VOICE_MODE": False,
    }
    for key, value in overrides.items():
        setattr(cfg, key, value)


def format_stable_mode_banner() -> str:
    mode = voice_runtime_mode()
    if is_realtime_experimental_mode():
        import config as cfg

        return (
            "Voice runtime mode: REALTIME EXPERIMENTAL\n"
            f"  realtime TTS: {getattr(cfg, 'REALTIME_TTS_ENABLED', False)}\n"
            f"  voice guard: {getattr(cfg, 'VOICE_COMMAND_GUARD_ENABLED', False)}\n"
            f"  primary backend: {getattr(cfg, 'TTS_PRIMARY_BACKEND', 'realtime')}\n"
            f"  fallback backend: {getattr(cfg, 'TTS_FALLBACK_BACKEND', 'pyttsx3_direct')}\n"
            f"  human conversational runtime: {getattr(cfg, 'HUMAN_CONVERSATIONAL_RUNTIME_ENABLED', False)}"
        )
    if not is_stable_voice_mode():
        return f"Voice runtime mode: {mode or 'default'}"
    import config as cfg

    return (
        "Voice runtime mode: STABLE (known-good baseline)\n"
        f"  STT: {cfg.STT_MODEL} cpu/{cfg.STT_COMPUTE_TYPE} beam={cfg.STT_BEAM_SIZE}\n"
        f"  streaming={cfg.STT_STREAMING_BUFFER_ENABLED} multipass={cfg.STT_MULTIPASS_ENABLED} "
        f"stack={cfg.STT_STACK_ENABLED}\n"
        f"  TTS: {cfg.TTS_FORCE_ENGINE or cfg.TTS_ENGINE} backend={getattr(cfg, 'TTS_BACKEND', '')} "
        f"async={cfg.TTS_ASYNC} safe_mode={cfg.TTS_SAFE_MODE}\n"
        f"  timeouts: record={cfg.STT_MAX_RECORD_SECONDS}s stt={cfg.STT_TIMEOUT_SECONDS}s "
        f"tts={cfg.TTS_TIMEOUT_SECONDS}s"
    )
