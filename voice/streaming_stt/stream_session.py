"""Streaming STT session — rolling buffer, partials, endpoint, prefetch."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

import config as cfg
from config import STT_SAMPLE_RATE, STT_SILENCE_THRESHOLD
from core.logger import setup_logger
from voice.streaming_stt.endpoint_detector import EndpointState, StreamEndpointDetector
from voice.streaming_stt.incremental_decode import IncrementalDecoder, TranscribeFn, default_transcribe_fn
from voice.streaming_stt.intent_prefetch import prefetch_intent
from voice.streaming_stt.realtime_metrics import RealtimeSttMetrics, publish_metrics, reset_realtime_metrics
from voice.streaming_stt.rolling_buffer import RollingAudioBuffer
from voice.streaming_stt.session_policy import StreamingSttFallbackError
from voice.voice_turn_diagnostics import (
    begin_turn as begin_voice_turn_diagnostics,
    note_chunk as note_voice_chunk_diagnostics,
    note_endpoint as note_voice_endpoint_reason,
    note_silence as note_voice_silence,
    note_speech_detected as note_voice_speech_detected,
)
from voice.stt_stack.partial_stream import emit_partial

logger = setup_logger("jarvis.voice.streaming.session")


def _clamp_buffer_seconds(value: float | None) -> float:
    raw = cfg.STT_ROLLING_BUFFER_SECONDS if value is None else float(value)
    return min(3.0, max(1.5, raw))


def _mono_float32(chunk: np.ndarray) -> np.ndarray:
    flat = np.squeeze(chunk).astype(np.float32, copy=False)
    if flat.ndim > 1:
        flat = flat[:, 0]
    return flat


@dataclass
class StreamingSttResult:
    text: str
    partial_updates: int
    decode_ms: float
    record_seconds: float
    endpoint_silence_ms: float
    prefetch_intent: str = ""
    prefetch_confidence: float = 0.0
    early_ack: str = ""
    conversation_intent: str = ""
    conversation_confidence: float = 0.0
    planned_intents: tuple[str, ...] = ()
    turn_phase: str = ""
    semantic_over_budget: bool = False


def is_streaming_stt_enabled() -> bool:
    try:
        import config as _cfg

        if getattr(_cfg, "VOICE_RUNTIME_STABLE", False):
            return False
    except Exception:
        pass
    from voice.streaming_stt.session_policy import is_streaming_stt_enabled_for_session

    return is_streaming_stt_enabled_for_session()


class StreamingSttSession:
    """
    Continuous mic → rolling buffer → incremental partials → endpoint (stream stays up until session end).
  """

    def __init__(
        self,
        *,
        sample_rate: int | None = None,
        buffer_seconds: float | None = None,
        partial_interval_ms: float | None = None,
        transcribe_fn: TranscribeFn | None = None,
        chunk_samples: int | None = None,
        session_context: object | None = None,
        audio_feed: Callable[[], np.ndarray] | None = None,
        on_partial: Callable[[str], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate or STT_SAMPLE_RATE
        self.buffer_seconds = _clamp_buffer_seconds(buffer_seconds)
        self.partial_interval_s = max(
            0.05,
            (partial_interval_ms or cfg.STT_PARTIAL_INTERVAL_MS) / 1000.0,
        )
        self._transcribe_fn = transcribe_fn or default_transcribe_fn
        self._chunk_samples = (
            chunk_samples
            if chunk_samples is not None
            else cfg.streaming_chunk_samples(sample_rate=self.sample_rate)
        )
        self._session_context = session_context
        self._audio_feed = audio_feed
        self._on_partial = on_partial
        self._buffer = RollingAudioBuffer(
            sample_rate=self.sample_rate,
            max_seconds=self.buffer_seconds,
        )
        self._endpoint = StreamEndpointDetector(
            silence_threshold=STT_SILENCE_THRESHOLD,
            endpoint_silence_ms=cfg.STT_STREAM_ENDPOINT_SILENCE_MS,
            min_speech_ms=cfg.STT_STREAM_MIN_SPEECH_MS,
            sample_rate=self.sample_rate,
            chunk_seconds=self._chunk_samples / float(self.sample_rate),
        )
        self._decoder = IncrementalDecoder(
            transcribe_fn=self._transcribe_fn,
            min_interval_ms=cfg.STT_INCREMENTAL_DECODE_MIN_MS,
            min_new_samples=int(
                self.sample_rate * (0.1 + cfg.STT_STREAM_OVERLAP_MS / 1000.0)
            ),
        )
        self._stop = threading.Event()
        self._stream: object | None = None
        self._partial_count = 0
        self._last_partial_text = ""
        self._last_decode_ms = 0.0
        self._barge_done = False
        self._final_chunks: list[np.ndarray] = []
        self._endpoint_finalized = False
        self._last_endpoint_state = EndpointState()
        self._last_prefetch_intent = ""
        self._last_prefetch_conf = 0.0
        self._early_ack = ""
        self._conv_intent = ""
        self._conv_conf = 0.0
        self._planned: tuple[str, ...] = ()
        self._turn_phase = ""
        self._semantic_over_budget = False
        self._run_started_monotonic = 0.0
        self._last_chunk_mono = 0.0

    def feed_audio(self, chunk: np.ndarray) -> None:
        """Test hook / external feeder."""
        self._process_chunk(chunk)

    def _process_chunk(self, chunk: np.ndarray) -> None:
        now = time.monotonic()
        if self._last_chunk_mono > 0:
            gap_ms = (now - self._last_chunk_mono) * 1000.0
            try:
                from voice.streaming_stt.diagnostics import mark_chunk_gap_overload

                mark_chunk_gap_overload(
                    gap_ms,
                    expected_ms=cfg.STT_STREAM_CHUNK_MS,
                )
            except Exception:
                pass
        self._last_chunk_mono = now
        mono = _mono_float32(chunk)
        try:
            from voice.streaming_stt.diagnostics import mark_audio_chunk

            mark_audio_chunk(mono.size)
        except Exception:
            pass
        tts_active = False
        try:
            from voice.streaming_player import is_speaking

            tts_active = bool(is_speaking())
        except Exception:
            pass
        # Avoid treating JARVIS TTS playback as user speech before speech starts.
        if tts_active and not self._endpoint.speech_started:
            return
        self._buffer.append(chunk)
        state = self._endpoint.observe_chunk(chunk)
        self._last_endpoint_state = state
        note_voice_chunk_diagnostics(
            energy=state.energy,
            vad_probability=state.vad_probability,
            tts_active=tts_active,
        )
        note_voice_silence(silence_ms=state.silence_ms)
        if state.speech_detected:
            note_voice_speech_detected()
            try:
                from voice.streaming_stt.diagnostics import mark_vad_speech_started

                mark_vad_speech_started()
            except Exception:
                pass
        if state.speech_detected and not self._endpoint_finalized:
            self._final_chunks.append(_mono_float32(chunk).copy())
        if state.endpoint_reached and not self._endpoint_finalized:
            self._endpoint_finalized = True
            note_voice_endpoint_reason("silence_after_speech")
            if self._run_started_monotonic > 0:
                try:
                    from voice.latency_tracker import mark_endpoint

                    mark_endpoint((time.monotonic() - self._run_started_monotonic) * 1000.0)
                except Exception:
                    pass
        try:
            import config as _cfg

            if _cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED and _cfg.CONV_INTERRUPTION_ENABLED:
                from conversation.semantic_stream.interruption_handler import (
                    handle_streaming_interruption,
                )

                handle_streaming_interruption(speech_detected=state.speech_detected)
        except Exception:
            pass
        if state.speech_detected and not self._barge_done:
            self._barge_done = True
            try:
                from config import TTS_BARGE_IN_ENABLED

                if TTS_BARGE_IN_ENABLED:
                    from voice.streaming_player import is_speaking

                    if is_speaking():
                        from voice.human_conversation import interrupt_on_user_speech_start

                        interrupt_on_user_speech_start()
            except Exception:
                pass

    def _final_audio_snapshot(self) -> np.ndarray:
        if not self._final_chunks:
            return np.array([], dtype=np.float32)
        if len(self._final_chunks) == 1:
            return self._final_chunks[0].copy()
        return np.concatenate(self._final_chunks, axis=0).copy()

    def _maybe_partial(self) -> None:
        if not self._endpoint.speech_started:
            return
        if self._buffer.duration_seconds() * 1000.0 < cfg.STT_STREAM_MIN_PARTIAL_CONTEXT_MS:
            return
        if not self._decoder.should_decode(
            total_samples=self._buffer.total_samples,
            generation=self._buffer.generation,
        ):
            return
        t0 = time.perf_counter()
        audio = self._buffer.snapshot()
        try:
            from voice.streaming_stt.diagnostics import mark_inference_start

            mark_inference_start()
        except Exception:
            pass
        try:
            text = self._decoder.decode(
                audio,
                sample_rate=self.sample_rate,
                generation=self._buffer.generation,
            )
        except StreamingSttFallbackError as exc:
            from voice.streaming_stt.session_policy import audio_flowing_for_session

            if audio_flowing_for_session():
                logger.warning(
                    "partial decode timeout with audio flowing; keeping stream alive: %s",
                    exc,
                )
                return
            raise
        decode_ms = (time.perf_counter() - t0) * 1000.0
        self._last_decode_ms = decode_ms
        try:
            from voice.streaming_stt.diagnostics import mark_inference_end

            mark_inference_end(decode_ms)
        except Exception:
            pass
        if text and text.strip() != self._last_partial_text:
            emit_partial(text)
            self._last_partial_text = text.strip()
            if self._partial_count == 0 and self._run_started_monotonic > 0:
                try:
                    from voice.latency_tracker import mark_first_partial

                    mark_first_partial((time.monotonic() - self._run_started_monotonic) * 1000.0)
                except Exception:
                    pass
                try:
                    from voice.streaming_stt.diagnostics import mark_first_partial as mark_diag_first

                    mark_diag_first(text.strip())
                except Exception:
                    pass
            self._partial_count += 1
            if self._on_partial is not None:
                try:
                    self._on_partial(text.strip())
                except Exception:
                    pass
            try:
                import config as _cfg

                if _cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED:
                    from conversation.semantic_stream.engine import on_partial_transcript

                    conv = on_partial_transcript(
                        text,
                        session_context=self._session_context,
                        speech_detected=True,
                        is_final=False,
                    )
                    self._conv_intent = conv.primary_intent
                    self._conv_conf = conv.confidence
                    self._planned = conv.planned_actions
                    self._turn_phase = conv.turn_phase
                    if conv.profile:
                        self._semantic_over_budget = conv.profile.over_budget
            except Exception:
                pass
            try:
                from voice.streaming_pipeline import get_streaming_pipeline

                pipe = get_streaming_pipeline(session_context=self._session_context)
                pipe.push_partial(text.strip())
            except Exception:
                pass
            prefetch = prefetch_intent(text, session_context=self._session_context)
            if prefetch is not None:
                self._last_prefetch_intent = prefetch.intent
                self._last_prefetch_conf = prefetch.confidence
        publish_metrics(
            RealtimeSttMetrics(
                partial_interval_ms=self.partial_interval_s * 1000.0,
                last_partial_ms=self.partial_interval_s * 1000.0,
                last_decode_ms=decode_ms,
                buffer_seconds=self._buffer.duration_seconds(),
                partial_count=self._partial_count,
                prefetch_intent=self._last_prefetch_intent,
                prefetch_confidence=self._last_prefetch_conf,
                endpoint_silence_ms=self._last_endpoint_state.silence_ms,
                gpu_first=bool(cfg.STT_STREAM_GPU_FIRST),
                stream_active=True,
            )
        )

    def _start_mic(self) -> None:
        if self._audio_feed is not None:
            return
        import sounddevice as sd

        try:
            from voice.streaming_stt.diagnostics import mark_thread_started

            mark_thread_started()
        except Exception:
            pass

        def callback(indata, _frames, _time, status) -> None:
            if status:
                logger.warning("stream mic status: %s", status)
            if self._stop.is_set():
                return
            self._process_chunk(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self._chunk_samples,
            callback=callback,
        )
        self._stream.start()
        try:
            from voice.streaming_stt.diagnostics import mark_mic_opened

            mark_mic_opened()
        except Exception:
            pass

    def _stop_mic(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def run_until_endpoint(self, *, max_seconds: float) -> StreamingSttResult:
        """Block until endpoint silence or max_seconds."""
        reset_realtime_metrics()
        self._stop.clear()
        self._endpoint.reset()
        self._buffer.clear()
        self._final_chunks.clear()
        self._endpoint_finalized = False
        self._last_endpoint_state = EndpointState()
        self._partial_count = 0
        self._last_partial_text = ""
        self._last_decode_ms = 0.0
        self._barge_done = False
        self._last_prefetch_intent = ""
        self._last_prefetch_conf = 0.0
        self._early_ack = ""
        self._conv_intent = ""
        self._conv_conf = 0.0
        self._planned = ()
        self._turn_phase = ""
        self._semantic_over_budget = False
        started = time.monotonic()
        self._run_started_monotonic = started
        begin_voice_turn_diagnostics()
        last_partial_tick = started
        record_started = started

        if self._audio_feed is not None:
            try:
                from voice.streaming_stt.diagnostics import mark_thread_started

                mark_thread_started()
            except Exception:
                pass
            feeder = threading.Thread(target=self._run_feeder, args=(max_seconds,), daemon=True)
            feeder.start()
        else:
            self._start_mic()

        try:
            from ui.overlay_app import notify_overlay_listening

            notify_overlay_listening()
        except Exception:
            pass

        publish_metrics(
            RealtimeSttMetrics(
                partial_interval_ms=self.partial_interval_s * 1000.0,
                buffer_seconds=0.0,
                gpu_first=bool(cfg.STT_STREAM_GPU_FIRST),
                stream_active=True,
            )
        )

        final_text = ""
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                elapsed = now - started
                if elapsed >= max_seconds:
                    logger.info("streaming STT max_seconds=%.1f reached", max_seconds)
                    note_voice_endpoint_reason("max_seconds")
                    break
                if self._endpoint.endpoint_reached:
                    logger.info("streaming STT endpoint at %.1fs", elapsed)
                    note_voice_endpoint_reason("silence_after_speech")
                    break
                if now - last_partial_tick >= self.partial_interval_s:
                    try:
                        self._maybe_partial()
                    except StreamingSttFallbackError:
                        raise
                    last_partial_tick = now
                time.sleep(0.02)
            if not self._endpoint.endpoint_reached:
                try:
                    self._maybe_partial()
                except StreamingSttFallbackError:
                    raise
            final_text = self._decoder.text
            audio_final = self._final_audio_snapshot()
            if audio_final.size == 0:
                audio_final = self._buffer.snapshot()
            if audio_final.size > 0:
                try:
                    from voice.streaming_stt.transcribe import transcribe_stream_final

                    t_final = time.perf_counter()
                    final_text = transcribe_stream_final(
                        audio_final,
                        self.sample_rate,
                        partial_text=final_text,
                    )
                    self._last_decode_ms = (time.perf_counter() - t_final) * 1000.0
                    try:
                        from voice.latency_tracker import set_final_transcript_ms

                        set_final_transcript_ms(self._last_decode_ms)
                    except Exception:
                        pass
                except StreamingSttFallbackError:
                    raise
            try:
                import config as _cfg

                if _cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED and final_text:
                    from conversation.semantic_stream.engine import on_partial_transcript

                    conv = on_partial_transcript(
                        final_text,
                        session_context=self._session_context,
                        speech_detected=True,
                        is_final=True,
                    )
                    self._conv_intent = conv.primary_intent
                    self._conv_conf = conv.confidence
                    self._planned = conv.planned_actions
                    self._turn_phase = conv.turn_phase
                    if conv.reformulated_text:
                        final_text = conv.reformulated_text
            except Exception:
                pass
        finally:
            self._stop_mic()
            try:
                from voice.streaming_stt.diagnostics import mark_stream_alive

                mark_stream_alive(False)
            except Exception:
                pass
            publish_metrics(
                RealtimeSttMetrics(
                    partial_interval_ms=self.partial_interval_s * 1000.0,
                    last_decode_ms=self._last_decode_ms,
                    buffer_seconds=self._buffer.duration_seconds(),
                    partial_count=self._partial_count,
                    prefetch_intent=self._last_prefetch_intent,
                    prefetch_confidence=self._last_prefetch_conf,
                    stream_active=False,
                    gpu_first=bool(cfg.STT_STREAM_GPU_FIRST),
                )
            )

        record_seconds = time.monotonic() - record_started
        return StreamingSttResult(
            text=(final_text or "").strip(),
            partial_updates=self._partial_count,
            decode_ms=self._last_decode_ms,
            record_seconds=record_seconds,
            endpoint_silence_ms=self._last_endpoint_state.silence_ms,
            prefetch_intent=self._last_prefetch_intent,
            prefetch_confidence=self._last_prefetch_conf,
            early_ack=self._early_ack,
            conversation_intent=self._conv_intent,
            conversation_confidence=self._conv_conf,
            planned_intents=self._planned,
            turn_phase=self._turn_phase,
            semantic_over_budget=self._semantic_over_budget,
        )

    def _run_feeder(self, max_seconds: float) -> None:
        deadline = time.monotonic() + max_seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            if self._audio_feed is None:
                break
            chunk = self._audio_feed()
            if chunk is not None and chunk.size > 0:
                self._process_chunk(chunk)
            time.sleep(self._chunk_samples / float(self.sample_rate))


def run_streaming_wake_capture(
    max_seconds: float,
    *,
    session_context: object | None = None,
    transcribe_fn: TranscribeFn | None = None,
    audio_feed: Callable[[], np.ndarray] | None = None,
) -> StreamingSttResult:
    """Wake-session capture using rolling-buffer streaming STT."""
    session = StreamingSttSession(
        session_context=session_context,
        transcribe_fn=transcribe_fn,
        audio_feed=audio_feed,
    )
    return session.run_until_endpoint(max_seconds=max_seconds)
