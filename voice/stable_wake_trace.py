"""Structured wake-session logging for stable voice runtime."""

from __future__ import annotations

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.stable_wake")


def log_stable_wake_stage(
    *,
    stage: str,
    record_seconds: float | None = None,
    wav_path: str | None = None,
    raw_transcript: str = "",
    normalized_transcript: str = "",
    intent: str = "",
    confidence: float | None = None,
    router_called: bool | None = None,
    extra: str = "",
) -> None:
    try:
        from voice.runtime_mode import is_stable_voice_mode

        if not is_stable_voice_mode():
            return
    except Exception:
        return
    parts = [f"stable_wake {stage}"]
    if record_seconds is not None:
        parts.append(f"record_s={record_seconds:.2f}")
    if wav_path:
        parts.append(f"wav={wav_path}")
    if raw_transcript:
        parts.append(f"raw={raw_transcript!r}")
    if normalized_transcript:
        parts.append(f"norm={normalized_transcript!r}")
    if intent:
        parts.append(f"intent={intent}")
    if confidence is not None:
        parts.append(f"conf={confidence:.2f}")
    if router_called is not None:
        parts.append(f"router={'yes' if router_called else 'no'}")
    if extra:
        parts.append(extra)
    logger.info(" | ".join(parts))
