"""Audio/TTS runtime initialization — debug flags, pipeline v2 assert, status wiring."""

from __future__ import annotations

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.audio_runtime_init")


def initialize_audio_runtime_at_startup() -> None:
    """
    Apply debug audio bypass, register completion pipeline v2, and fail fast if stale.
    Must run once during JARVIS startup before any speech command.
    """
    from voice.audio_status import apply_force_audio_success_for_debug_at_startup

    apply_force_audio_success_for_debug_at_startup()

    from voice.pyttsx3_completion import assert_completion_pipeline_v2_at_startup

    assert_completion_pipeline_v2_at_startup()

    try:
        from voice.duplex_runtime import enable_full_duplex_runtime

        enable_full_duplex_runtime()
    except Exception as exc:
        logger.debug("Duplex runtime init skipped: %s", exc)

    try:
        from voice.providers.elevenlabs_websocket import prewarm_elevenlabs_websocket_at_startup

        prewarm_elevenlabs_websocket_at_startup()
    except Exception as exc:
        logger.debug("ElevenLabs websocket prewarm skipped: %s", exc)

    try:
        from conversation.human_runtime import enable_human_conversational_runtime

        enable_human_conversational_runtime()
    except Exception as exc:
        logger.debug("Human conversational runtime init skipped: %s", exc)

    try:
        from assistant.idle_proactive import start_idle_proactive_intelligence

        start_idle_proactive_intelligence()
    except Exception as exc:
        logger.debug("Idle proactive init skipped: %s", exc)

    try:
        from voice.audio_status import validate_audio_status_model

        validate_audio_status_model()
    except Exception as exc:
        logger.warning("Audio status model validation failed: %s", exc)
