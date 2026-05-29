"""Post-wake listening session → STT → router (no direct execution)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.logger import setup_logger
from voice.fast_voice import (
    effective_wake_cooldown_seconds,
    resolve_wake_listen_seconds,
)
from voice.latency_tracker import (
    begin_voice_command,
    finish_and_log,
    mark_wake_detected,
    set_record_ms,
    set_transcribe_ms,
)
from voice.microphone import MicrophoneError
from voice.privacy import ensure_no_audio_persistence
from config import STT_LOW_CONFIDENCE_BLOCK_WAKE
from voice.normalization import normalize_wake_transcript
from voice.stt_handling import handle_wake_low_confidence, record_stt_result
from voice.transcriber import TranscriptionError, transcribe_audio_detailed
from voice.voice_loop import process_voice_transcript
from voice.wakeword import WakeWordDetector

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.voice.wakeword_loop")

from voice.stt_empty_guidance import notify_empty_wake_transcript

_session_lock = threading.Lock()
_detector: WakeWordDetector | None = None


def record_for_seconds(seconds: float, *, wake_session: bool = True):
    """Resolve microphone capture at call time so tests can patch either import path."""
    from voice.microphone import record_for_seconds as _record_for_seconds

    return _record_for_seconds(seconds, wake_session=wake_session)


def run_post_wake_listening_session(
    app: "JarvisApp",
    *,
    session_already_acquired: bool = False,
) -> None:
    """
    Temporary record → STT → handle_text_command.
    Never called from wake word without going through router.
    """
    runtime = app.runtime
    acquired_session = session_already_acquired
    if not acquired_session and not runtime.acquire_wake_listening_session():
        logger.debug("Skipping wake session — another session active")
        try:
            from config import WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS
            from voice.wake_diagnostics import record_false_trigger_cooldown

            runtime.start_wake_cooldown(WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS)
            record_false_trigger_cooldown()
        except Exception:
            pass
        return

    acquired_session = True

    from ui.overlay_app import (
        notify_overlay_error,
        notify_overlay_heard_transcript,
        notify_overlay_listening,
        notify_overlay_transcribing,
        notify_overlay_transcript,
    )
    from voice.wake_greeting import play_wake_greeting_async, strip_wake_phrase_from_transcript

    try:
        from config import TTS_BARGE_IN_ENABLED

        if TTS_BARGE_IN_ENABLED:
            from voice.speech_controller import barge_in_if_speaking

            barge_in_if_speaking()
    except Exception:
        pass
    begin_voice_command(source="wakeword")
    mark_wake_detected(0.0)

    wake_listen = resolve_wake_listen_seconds()
    listen_seconds = wake_listen.wake_listen_seconds
    logger.info(
        "wake_session: listen_seconds=%.1f source=%s mode=%s",
        listen_seconds,
        wake_listen.source,
        wake_listen.mode,
    )
    notify_overlay_listening()
    play_wake_greeting_async(app)

    try:
        from conversation.human_runtime import (
            run_human_conversation_session,
            should_start_human_session_after_wake,
        )

        handoff = should_start_human_session_after_wake(app)
        try:
            from voice.tts_policy_trace import log_tts_policy_context

            log_tts_policy_context(
                stage="wake_session.handoff_decision",
                voice_path="wakeword_loop",
                input_mode="wakeword",
                extra={"handoff_to_human_session": handoff},
            )
        except Exception:
            pass
        if handoff:
            logger.info("wake_session: handoff to active human conversation session (Phase 59.1)")
            run_human_conversation_session(app=app)
            finish_and_log()
            return
        logger.info(
            "wake_session: discrete path (human session handoff declined — check STT_STREAMING_BUFFER_ENABLED / stable mode)"
        )
    except Exception as exc:
        logger.exception(
            "Human conversation session handoff failed, using discrete wake: %s",
            exc,
        )

    wav_path: Path | None = None
    stt_result = None
    streaming_attempted = False
    stable_mode = False
    try:
        from voice.runtime_mode import is_stable_voice_mode

        stable_mode = is_stable_voice_mode()
    except Exception:
        stable_mode = False
    try:
        try:
            from voice.streaming_stt import is_streaming_stt_enabled, reset_streaming_session

            reset_streaming_session()
            use_streaming = is_streaming_stt_enabled() and not stable_mode
        except Exception:
            use_streaming = False

        if use_streaming:
            streaming_attempted = True
            try:
                from voice.streaming_stt import run_streaming_wake_capture

                logger.info(
                    "wake_session: streaming buffer start listen_seconds=%.1f",
                    listen_seconds,
                )
                t_rec = time.perf_counter()
                stream_out = run_streaming_wake_capture(
                    listen_seconds,
                    session_context=app.session if hasattr(app, "session") else None,
                )
                record_ms = (time.perf_counter() - t_rec) * 1000.0
                set_record_ms(record_ms)
                notify_overlay_transcribing()
                transcribe_ms = max(0.0, record_ms * 0.35)
                set_transcribe_ms(transcribe_ms)
                from voice.transcriber import TranscriptionResult

                stt_result = TranscriptionResult(
                    text=stream_out.text,
                    language="en",
                    model="streaming_buffer",
                    device="local",
                    compute_type="incremental",
                    low_confidence=not (stream_out.text or "").strip(),
                    backends_used=["streaming_buffer"],
                    fused_confidence=0.85 if stream_out.text else 0.0,
                )
                text = stt_result.text
                logger.info(
                    "wake_session: streaming end partials=%s text=%r",
                    stream_out.partial_updates,
                    text[:80],
                )
            except Exception as exc:
                logger.warning("Streaming STT failed, fallback record: %s", exc)
                use_streaming = False
                try:
                    from voice.streaming_stt.session_policy import (
                        disable_streaming_for_session,
                        is_streaming_stt_enabled_for_session,
                    )

                    if not is_streaming_stt_enabled_for_session():
                        disable_streaming_for_session(f"wake_stream_error:{exc}")
                except Exception:
                    pass

        if not use_streaming:
            try:
                logger.info(
                    "wake_session: recording start listen_seconds=%.1f wake_session=True",
                    listen_seconds,
                )
                t_rec = time.perf_counter()
                wav_path = record_for_seconds(listen_seconds, wake_session=True)
                record_ms = (time.perf_counter() - t_rec) * 1000.0
                set_record_ms(record_ms)
                logger.info(
                    "wake_session: recording end ms=%.0f path=%s",
                    record_ms,
                    wav_path,
                )
                if stable_mode:
                    from voice.stable_wake_trace import log_stable_wake_stage

                    log_stable_wake_stage(
                        stage="recorded",
                        record_seconds=record_ms / 1000.0,
                        wav_path=str(wav_path) if wav_path else None,
                    )
            except MicrophoneError as exc:
                runtime.increment_wake_error(str(exc))
                notify_overlay_error(str(exc))
                logger.warning("Wake listen record failed: %s", exc)
                finish_and_log()
                return

            notify_overlay_transcribing()
            try:
                t_stt = time.perf_counter()
                if stable_mode or streaming_attempted:
                    from voice.transcriber import transcribe_wake_audio_fast

                    stt_result = transcribe_wake_audio_fast(wav_path)
                else:
                    stt_result = transcribe_audio_detailed(wav_path)
                transcribe_ms = (time.perf_counter() - t_stt) * 1000.0
                set_transcribe_ms(transcribe_ms)
                text = stt_result.text
                if stable_mode:
                    from voice.stable_wake_trace import log_stable_wake_stage

                    log_stable_wake_stage(
                        stage="stt_done",
                        raw_transcript=text,
                        extra=f"ms={transcribe_ms:.0f}",
                    )
            except TranscriptionError as exc:
                runtime.increment_wake_error(str(exc))
                notify_overlay_error(str(exc))
                logger.warning("Wake STT failed: %s", exc)
                finish_and_log()
                return
            finally:
                ensure_no_audio_persistence(wav_path)
                wav_path = None

        raw_text = text
        logger.info("wake_session: transcript before strip=%r", raw_text)
        stripped = strip_wake_phrase_from_transcript(text)
        from voice.command_input import prepare_command_text

        text = prepare_command_text(normalize_wake_transcript(stripped))
        logger.info("wake_session: transcript after strip/normalize=%r", text)
        notify_overlay_heard_transcript(raw_text, text)
        empty_after = not text.strip()
        try:
            from config import WAKE_MIN_SPEECH_SECONDS
            from voice.microphone import get_last_capture_stats
            from voice.wake_diagnostics import (
                estimate_clipped_session,
                record_wake_session,
            )

            cap = get_last_capture_stats()
            speech_ms = (cap.speech_seconds * 1000.0) if cap else 0.0
            session_ms = (cap.session_seconds * 1000.0) if cap else record_ms
            silence_ms = (cap.silence_cutoff_seconds * 1000.0) if cap else 0.0
            clipped = estimate_clipped_session(
                raw_text=raw_text,
                normalized_text=text,
                speech_ms=speech_ms,
                empty_after_wake=empty_after,
                min_command_speech_ms=WAKE_MIN_SPEECH_SECONDS * 1000.0,
            )
            record_wake_session(
                session_ms=session_ms,
                speech_ms=speech_ms,
                silence_cutoff_ms=silence_ms,
                stt_ms=transcribe_ms,
                empty_after_wake=empty_after,
                clipped=clipped,
                raw_transcript=raw_text,
                normalized_transcript=text,
                corrected_transcript=stt_result.text,
            )
        except Exception:
            pass
        record_stt_result(
            stt_result,
            transcribe_ms=transcribe_ms,
            empty=empty_after,
            raw_text=raw_text,
            normalized_text=text,
        )
        if stt_result.low_confidence and STT_LOW_CONFIDENCE_BLOCK_WAKE:
            logger.info("wake_session: low confidence — repeat prompt, no route")
            handle_wake_low_confidence(
                app,
                stt_result,
                overlay_enabled=runtime.overlay_enabled,
            )
            finish_and_log()
            return
        if empty_after:
            from voice.stt_diagnostics import record_wake_retry

            record_wake_retry()
            logger.info(
                "wake_session: empty after strip — overlay error, handle_text_command=False"
            )
            if stable_mode:
                from voice.stable_wake_trace import log_stable_wake_stage

                log_stable_wake_stage(
                    stage="empty_transcript",
                    raw_transcript=raw_text,
                    normalized_transcript=text,
                    router_called=False,
                )
            notify_overlay_error(notify_empty_wake_transcript())
            finish_and_log()
            return

        notify_overlay_transcript(text)

        preview_intent = ""
        preview_conf = 0.0
        try:
            from brain.intent_classifier import classify_rules

            preview = classify_rules(text)
            preview_intent = preview.intent.value
            preview_conf = float(preview.confidence)
            logger.info(
                "wake_session: classify intent=%s confidence=%.2f",
                preview_intent,
                preview_conf,
            )
            if stable_mode:
                from voice.stable_wake_trace import log_stable_wake_stage

                log_stable_wake_stage(
                    stage="classified",
                    raw_transcript=raw_text,
                    normalized_transcript=text,
                    intent=preview_intent,
                    confidence=preview_conf,
                    router_called=True,
                )
        except Exception as exc:
            logger.debug("wake classify preview failed: %s", exc)

        logger.info("wake_session: calling handle_text_command via process_voice_transcript")
        # Only path to commands — same as push-to-talk
        process_voice_transcript(
            app,
            text,
            input_mode="wakeword",
            print_result=False,
            source="wakeword",
        )
    except Exception as exc:
        runtime.increment_wake_error(str(exc))
        from ui.overlay_app import notify_overlay_error

        notify_overlay_error(str(exc))
        logger.warning("Wake listening session error: %s", exc)
        finish_and_log()
    finally:
        ensure_no_audio_persistence(wav_path)
        runtime.start_wake_cooldown(effective_wake_cooldown_seconds())
        if acquired_session:
            runtime.release_wake_listening_session()


def _start_post_wake_session_thread(app: "JarvisApp") -> bool:
    runtime = app.runtime
    if not runtime.acquire_wake_listening_session():
        logger.debug("Skipping wake session thread - another session active")
        try:
            from config import WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS
            from voice.wake_diagnostics import record_false_trigger_cooldown

            runtime.start_wake_cooldown(WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS)
            record_false_trigger_cooldown()
        except Exception:
            pass
        return False

    try:
        threading.Thread(
            target=run_post_wake_listening_session,
            args=(app,),
            kwargs={"session_already_acquired": True},
            name="jarvis-wake-listen",
            daemon=True,
        ).start()
    except Exception:
        runtime.start_wake_cooldown(effective_wake_cooldown_seconds())
        runtime.release_wake_listening_session()
        raise
    return True


def start_wakeword_loop(app: "JarvisApp") -> WakeWordDetector:
    """Start background detector; returns handle for stop/toggle."""
    global _detector

    def _on_wake(_score: float) -> None:
        _start_post_wake_session_thread(app)

    _detector = WakeWordDetector(app, _on_wake)
    if not _detector.start():
        logger.warning("Wake word detector did not start (model missing or error)")
    return _detector


def stop_wakeword_loop(detector: WakeWordDetector | None = None) -> None:
    global _detector
    target = detector or _detector
    if target is not None:
        target.stop()
    if target is _detector:
        _detector = None


def get_active_detector() -> WakeWordDetector | None:
    return _detector
