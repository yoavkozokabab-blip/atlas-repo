"""Fast voice mode helpers (recording limits, no security changes)."""

from __future__ import annotations

import config as cfg


def _positive_seconds(value: float | int, fallback: float) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return fallback
    if seconds <= 0:
        return fallback
    return seconds


def effective_max_record_seconds(*, wake_session: bool = False) -> float:
    if wake_session:
        return effective_wake_listen_seconds()
    if cfg.FAST_VOICE_MODE:
        return _positive_seconds(cfg.STT_MAX_RECORD_SECONDS, 5.0)
    return float(cfg.STT_RECORDING_MAX_SECONDS)


def effective_wake_listen_seconds() -> float:
    try:
        from conversation.human_runtime import uses_continuous_conversation

        if uses_continuous_conversation():
            return max(8.0, float(getattr(cfg, "CONVERSATION_TURN_MAX_SECONDS", 45.0)))
    except Exception:
        pass
    wake_cap = _positive_seconds(getattr(cfg, "WAKE_MAX_LISTEN_SECONDS", 4.0), 4.0)
    if cfg.FAST_VOICE_MODE:
        return min(wake_cap, _positive_seconds(cfg.STT_MAX_RECORD_SECONDS, wake_cap))
    return wake_cap


def effective_wake_cooldown_seconds() -> float:
    return _positive_seconds(getattr(cfg, "WAKE_COOLDOWN_SECONDS", 4.0), 4.0)


def wake_early_stop_enabled() -> bool:
    return bool(getattr(cfg, "WAKE_EARLY_STOP_ENABLED", True))


def silence_stop_enabled() -> bool:
    return bool(cfg.STT_SILENCE_STOP_ENABLED)


def effective_wake_silence_seconds() -> float:
    """Tail silence after speech ends on wake capture (longer than aggressive PTT defaults)."""
    return _positive_seconds(
        getattr(cfg, "WAKE_SILENCE_SECONDS", cfg.STT_SILENCE_SECONDS),
        _positive_seconds(cfg.STT_SILENCE_SECONDS, 1.6),
    )


def effective_wake_post_speech_buffer_ms() -> float:
    try:
        return max(0.0, float(getattr(cfg, "WAKE_POST_SPEECH_BUFFER_MS", 700)))
    except (TypeError, ValueError):
        return 700.0


def effective_wake_min_speech_seconds() -> float:
    return _positive_seconds(getattr(cfg, "WAKE_MIN_SPEECH_SECONDS", 0.45), 0.45)


def effective_wake_min_total_seconds() -> float:
    return _positive_seconds(getattr(cfg, "WAKE_MIN_TOTAL_SECONDS", 0.6), 0.6)
