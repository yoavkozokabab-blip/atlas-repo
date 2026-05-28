"""Shared post-STT handling: diagnostics, low-confidence UX (no execution bypass)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import STT_LOW_CONFIDENCE_TTS_PROMPT
from voice.stt_diagnostics import record_transcription, record_wake_retry
from voice.transcriber import TranscriptionResult

if TYPE_CHECKING:
    from core.app import JarvisApp

LOW_CONFIDENCE_OVERLAY_MSG = "Low confidence — please repeat."


def record_stt_result(
    result: TranscriptionResult,
    *,
    transcribe_ms: float,
    empty: bool = False,
    raw_text: str = "",
    normalized_text: str = "",
) -> None:
    from config import STT_ENGINE
    from voice.voice_debug_store import record_transcript_debug

    record_transcription(
        model=result.model,
        engine=STT_ENGINE,
        duration_ms=transcribe_ms,
        low_confidence=result.low_confidence,
        empty=empty,
    )
    if raw_text or normalized_text:
        record_transcript_debug(
            raw=raw_text,
            normalized=normalized_text,
            avg_logprob=getattr(result, "avg_logprob", None),
            low_confidence=result.low_confidence,
        )


def notify_low_confidence(
    app: "JarvisApp | None",
    *,
    overlay_enabled: bool,
    speak_prompt: bool = False,
) -> None:
    if overlay_enabled:
        try:
            from ui.overlay_app import notify_overlay_error

            notify_overlay_error(LOW_CONFIDENCE_OVERLAY_MSG)
        except Exception:
            pass
    if speak_prompt and app is not None and getattr(app, "speak_enabled", False):
        if not STT_LOW_CONFIDENCE_TTS_PROMPT:
            return
        try:
            app.tts.speak("Please repeat your command.")
        except Exception:
            pass


def handle_wake_low_confidence(
    app: "JarvisApp",
    result: TranscriptionResult,
    *,
    overlay_enabled: bool,
) -> None:
    """Wake path: prompt user to repeat; do not route low-confidence text."""
    record_wake_retry()
    notify_low_confidence(
        app,
        overlay_enabled=overlay_enabled,
        speak_prompt=True,
    )
