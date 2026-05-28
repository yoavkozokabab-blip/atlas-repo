"""Streaming STT transcribe passes — fast partials, optional single final retry."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

import config as cfg
from core.logger import setup_logger
from voice.streaming_stt.session_policy import (
    StreamingSttFallbackError,
    block_accurate_retry_in_partial_loop,
    can_run_final_accurate_retry,
    mark_final_accurate_retry_used,
    record_partial_stt_timeout,
)

logger = setup_logger("jarvis.voice.streaming.transcribe")


def _write_temp_wav(audio: np.ndarray, sample_rate: int) -> Path:
    peak = float(np.max(np.abs(audio)))
    norm = audio if peak <= 1e-6 else audio / max(peak, 1.0)
    pcm = (norm * 32767).astype(np.int16)
    fd, name = tempfile.mkstemp(suffix=".wav", prefix="jarvis_stream_")
    path = Path(name)
    os.close(fd)
    wavfile.write(path, sample_rate, pcm)
    return path


def transcribe_stream_partial(audio: np.ndarray, sample_rate: int) -> str:
    """Fast partial decode only — no multipass, no accurate retry."""
    if audio.size == 0:
        return ""
    if block_accurate_retry_in_partial_loop():
        pass
    path = _write_temp_wav(audio, sample_rate)
    retries = max(0, int(getattr(cfg, "STT_STREAM_PARTIAL_RETRY_COUNT", 2)))
    try:
        from voice.transcriber import transcribe_faster_whisper_hypothesis

        beam = 1
        attempt = 0
        while True:
            attempt += 1
            try:
                from voice.streaming_stt.diagnostics import mark_partial_attempt

                mark_partial_attempt()
            except Exception:
                pass
            try:
                hyp = transcribe_faster_whisper_hypothesis(
                    path,
                    language="en",
                    beam_size=beam,
                    stt_pass="partial",
                )
                return (hyp.text or "").strip()
            except Exception as exc:
                from services.runtime_monitor import OperationTimeoutError

                if isinstance(exc, OperationTimeoutError):
                    disable = record_partial_stt_timeout()
                    if not disable and attempt <= retries + 1:
                        try:
                            from voice.streaming_stt.diagnostics import mark_partial_retry
                            from voice.streaming_stt.session_policy import audio_flowing_for_session

                            mark_partial_retry()
                        except Exception:
                            pass
                        if audio_flowing_for_session() or attempt <= retries:
                            logger.warning(
                                "stream partial timeout attempt %s (retrying): %s",
                                attempt,
                                exc,
                            )
                            continue
                    raise StreamingSttFallbackError(str(exc)) from exc
                logger.debug("stream partial transcribe failed: %s", exc)
                return ""
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def transcribe_stream_final(
    audio: np.ndarray,
    sample_rate: int,
    *,
    partial_text: str = "",
) -> str:
    """
    Final endpoint pass: fast decode, then at most one accurate retry if enabled.
    """
    text = (partial_text or "").strip()
    if audio.size == 0:
        return text
    path = _write_temp_wav(audio, sample_rate)
    try:
        from voice.transcriber import transcribe_faster_whisper_hypothesis

        fast = transcribe_faster_whisper_hypothesis(
            path,
            language="en",
            beam_size=1,
            stt_pass="partial",
        )
        fast_text = (fast.text or "").strip()
        if fast_text:
            text = fast_text

        if not can_run_final_accurate_retry():
            return text

        from voice.stt_stack.multipass import _should_accurate_retry, _preview_intent_unknown

        try:
            from voice.stt_stack.voice_fingerprint import grammar_min_score_for_user

            min_score = grammar_min_score_for_user()
        except Exception:
            min_score = cfg.VOICE_GRAMMAR_MIN_SCORE

        unknown = _preview_intent_unknown(text)
        close = False
        try:
            from voice.stt_stack.multipass import _close_match_detected

            close = _close_match_detected(text, min_score=min_score)
        except Exception:
            pass
        empty = not text
        if not _should_accurate_retry(
            text=text,
            low_confidence=empty,
            empty=empty,
            unknown_intent=unknown,
            close_match=close,
        ):
            return text

        mark_final_accurate_retry_used()
        accurate = transcribe_faster_whisper_hypothesis(
            path,
            language="en",
            beam_size=cfg.STT_ACCURATE_RETRY_BEAM_SIZE,
            stt_pass="accurate",
        )
        if (accurate.text or "").strip():
            return accurate.text.strip()
        return text
    except Exception as exc:
        from services.runtime_monitor import OperationTimeoutError

        if isinstance(exc, OperationTimeoutError):
            if record_partial_stt_timeout():
                raise StreamingSttFallbackError(str(exc)) from exc
            logger.warning("stream final timeout (streaming continues): %s", exc)
            return text
        logger.warning("stream final transcribe failed: %s", exc)
        return text
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
