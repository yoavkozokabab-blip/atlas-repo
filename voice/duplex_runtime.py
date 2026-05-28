"""Full-duplex voice runtime — STT active during TTS, energy barge-in (Phase 58)."""

from __future__ import annotations

import threading

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.duplex_runtime")

_enabled = False
_lock = threading.Lock()


def is_full_duplex_enabled() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "REALTIME_FULL_DUPLEX_ENABLED", True)) and _enabled
    except Exception:
        return _enabled


def enable_full_duplex_runtime() -> None:
    global _enabled
    with _lock:
        _enabled = True
    logger.info("Full-duplex voice runtime enabled")


def on_user_speech_energy_detected(*, partial_text: str = "") -> bool:
    """
    Immediate TTS pause/cancel when user speech energy detected.
    STT remains active (caller continues capture).
    """
    if not is_full_duplex_enabled():
        return False
    from voice.interruption_manager import cancel
    from voice.streaming_player import pause_playback_immediately

    pause_playback_immediately()
    cancelled = cancel()
    if cancelled or partial_text:
        logger.debug("Duplex barge-in: partial=%r cancelled=%s", partial_text[:40], cancelled)
    return cancelled


def show_duplex_runtime_status() -> str:
    from voice.streaming_player import is_playback_paused, is_speaking

    return (
        "Full-duplex voice runtime (Phase 58):\n"
        f"  enabled: {'yes' if is_full_duplex_enabled() else 'no'}\n"
        f"  speaking: {'yes' if is_speaking() else 'no'}\n"
        f"  playback_paused: {'yes' if is_playback_paused() else 'no'}"
    )


def reset_duplex_runtime_for_tests() -> None:
    global _enabled
    with _lock:
        _enabled = False
