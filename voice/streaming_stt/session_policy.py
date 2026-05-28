"""Per wake-session streaming STT policy (disable on repeated failure, guard retries)."""

from __future__ import annotations

import threading
import time

import config as cfg
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.streaming.policy")

_lock = threading.Lock()
_session_disabled = False
_disable_reason = ""
_partial_timeout_count = 0
_partial_timeout_grace_skipped = 0
_final_accurate_retry_used = False
_partial_accurate_retry_blocked = True
_session_started_mono = 0.0


class StreamingSttFallbackError(Exception):
    """Streaming STT failed; caller should fall back to legacy fast capture."""


def reset_streaming_session() -> None:
    global _session_disabled, _disable_reason, _partial_timeout_count, _partial_timeout_grace_skipped
    global _final_accurate_retry_used, _session_started_mono
    with _lock:
        _session_disabled = False
        _disable_reason = ""
        _partial_timeout_count = 0
        _partial_timeout_grace_skipped = 0
        _final_accurate_retry_used = False
        _session_started_mono = time.monotonic()
    try:
        from voice.streaming_stt.diagnostics import begin_streaming_diagnostics

        begin_streaming_diagnostics()
    except Exception:
        pass


def disable_streaming_for_session(reason: str) -> None:
    global _session_disabled, _disable_reason
    with _lock:
        if _session_disabled:
            return
        _session_disabled = True
        _disable_reason = (reason or "unknown")[:200]
    logger.warning("streaming STT disabled for session: %s", _disable_reason)
    try:
        from voice.streaming_stt.diagnostics import mark_stream_disabled

        mark_stream_disabled(_disable_reason)
    except Exception:
        pass


def streaming_session_disabled() -> bool:
    with _lock:
        return _session_disabled


def get_streaming_disable_reason() -> str:
    with _lock:
        return _disable_reason


def is_streaming_stt_enabled_for_session() -> bool:
    return bool(cfg.STT_STREAMING_BUFFER_ENABLED) and not streaming_session_disabled()


def _within_startup_grace() -> bool:
    with _lock:
        started = _session_started_mono
    if started <= 0:
        return True
    grace = float(getattr(cfg, "STT_STREAM_STARTUP_GRACE_SECONDS", 10.0))
    return (time.monotonic() - started) < max(0.0, grace)


def record_partial_stt_timeout() -> bool:
    """
    Record a partial decode timeout.

    Returns True only when streaming should be disabled (repeated failures).
    During startup grace or before max failures, streaming stays active.
    """
    global _partial_timeout_count, _partial_timeout_grace_skipped
    try:
        from voice.streaming_stt.diagnostics import mark_partial_timeout

        mark_partial_timeout()
    except Exception:
        pass

    if _within_startup_grace():
        with _lock:
            _partial_timeout_grace_skipped += 1
        logger.warning(
            "partial STT timeout during startup grace (%.1fs); streaming stays active",
            float(getattr(cfg, "STT_STREAM_STARTUP_GRACE_SECONDS", 10.0)),
        )
        return False

    with _lock:
        _partial_timeout_count += 1
        count = _partial_timeout_count
    max_failures = max(1, int(getattr(cfg, "STT_STREAM_PARTIAL_MAX_FAILURES", 3)))
    if count < max_failures:
        logger.warning(
            "partial STT timeout %s/%s; retrying streaming (not disabling yet)",
            count,
            max_failures,
        )
        return False

    disable_streaming_for_session(f"partial_stt_timeout x{count}")
    return True


def partial_timeout_count() -> int:
    with _lock:
        return _partial_timeout_count


def partial_timeout_grace_skipped() -> int:
    with _lock:
        return _partial_timeout_grace_skipped


def block_accurate_retry_in_partial_loop() -> bool:
    """Never run accurate retry during streaming partial decode."""
    return bool(_partial_accurate_retry_blocked or not cfg.STT_STREAM_PARTIAL_ACCURATE_RETRY_ENABLED)


def can_run_final_accurate_retry() -> bool:
    with _lock:
        if _final_accurate_retry_used:
            return False
    return bool(cfg.STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED)


def mark_final_accurate_retry_used() -> None:
    global _final_accurate_retry_used
    with _lock:
        _final_accurate_retry_used = True


def audio_flowing_for_session() -> bool:
    """True when mic chunks are arriving — delayed partials should not collapse session."""
    try:
        from voice.streaming_stt.diagnostics import get_streaming_diagnostics

        diag = get_streaming_diagnostics()
        if diag is None:
            return False
        return bool(diag.audio_frames_received and diag.chunks_received >= 2)
    except Exception:
        return False
