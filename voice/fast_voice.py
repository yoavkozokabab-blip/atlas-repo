"""Fast voice mode helpers (recording limits, no security changes)."""

from __future__ import annotations

import os
from dataclasses import dataclass

import config as cfg


@dataclass(frozen=True)
class WakeListenResolution:
    """Resolved wake listen window for diagnostics and capture."""

    wake_listen_seconds: float
    source: str
    mode: str  # stable | discrete | conversational


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


def resolve_wake_listen_seconds() -> WakeListenResolution:
    """Resolve wake listen duration.

    - stable / discrete post-wake capture: ``WAKE_MAX_LISTEN_SECONDS`` (default 5s)
    - active human conversational session: ``CONVERSATION_TURN_MAX_SECONDS`` (e.g. 45s)
    - enabling continuous conversation alone does *not* widen discrete wake capture
    """
    from conversation.human_runtime import is_session_active
    from voice.runtime_mode import is_stable_voice_mode

    if is_session_active():
        turn_max = max(
            8.0,
            _positive_seconds(
                getattr(cfg, "CONVERSATION_TURN_MAX_SECONDS", 45.0),
                45.0,
            ),
        )
        return WakeListenResolution(
            turn_max,
            "conversation_turn_max_seconds",
            "conversational",
        )

    wake_cap = _positive_seconds(getattr(cfg, "WAKE_MAX_LISTEN_SECONDS", 5.0), 5.0)
    source = (
        "env:WAKE_MAX_LISTEN_SECONDS"
        if os.getenv("WAKE_MAX_LISTEN_SECONDS") is not None
        else "wake_max_listen_seconds"
    )
    if cfg.FAST_VOICE_MODE:
        wake_cap = min(
            wake_cap,
            _positive_seconds(getattr(cfg, "STT_MAX_RECORD_SECONDS", wake_cap), wake_cap),
        )
        source = f"{source}+fast_voice_cap"

    mode = "stable" if is_stable_voice_mode() else "discrete"
    return WakeListenResolution(wake_cap, source, mode)


def effective_wake_listen_seconds() -> float:
    return resolve_wake_listen_seconds().wake_listen_seconds


def format_wake_listen_diagnostics() -> str:
    """Single-line wake listen resolution for status / debug output."""
    res = resolve_wake_listen_seconds()
    return (
        f"wake_listen_seconds={res.wake_listen_seconds:.1f} "
        f"source={res.source} mode={res.mode}"
    )


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
