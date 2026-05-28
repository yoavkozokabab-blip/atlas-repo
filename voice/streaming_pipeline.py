"""Streaming speech pipeline orchestrator (Phase 56)."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.streaming_pipeline")

_MAX_QUEUE = 32
_SPEECH_TIMEOUT_S = 30.0


@dataclass
class PipelineMetrics:
    partial_updates: int = 0
    predictions: int = 0
    interruptions: int = 0
    responses: int = 0
    last_latency_ms: float = 0.0


@dataclass
class StreamingPipeline:
    """Coordinates partial STT, prediction, interruption, and response prep."""

    session_context: object | None = None
    on_partial: Callable[[str], None] | None = None
    on_prediction: Callable[[object], None] | None = None
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    _partial_q: queue.Queue[str] = field(default_factory=lambda: queue.Queue(maxsize=_MAX_QUEUE))
    _worker: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _last_partial: str = ""

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._loop, name="jarvis-streaming-pipeline", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1.0)
        self._worker = None

    def push_partial(self, text: str) -> None:
        partial = (text or "").strip()
        if not partial:
            return
        self._last_partial = partial
        try:
            self._partial_q.put_nowait(partial)
        except queue.Full:
            try:
                self._partial_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._partial_q.put_nowait(partial)
            except queue.Full:
                pass

    def handle_user_speech_start(self, *, partial_text: str = "") -> None:
        from voice.interruption_manager import on_user_speech_detected

        result = on_user_speech_detected(partial_text=partial_text or self._last_partial)
        if result.stopped_tts:
            self.metrics.interruptions += 1

    def speak_response_stream(
        self,
        text_chunks,
        *,
        voice: str = "",
        rate_raw: str = "",
        emotion: str = "neutral",
    ) -> str:
        """Speak while response text is still being generated (Phase 57)."""
        try:
            from voice.realtime_tts import is_realtime_tts_enabled, speak_realtime, speak_realtime_parallel

            if is_realtime_tts_enabled():
                provider = speak_realtime_parallel(
                    iter(text_chunks),
                    voice=voice,
                    rate_raw=rate_raw,
                    emotion=emotion,
                )
            else:
                chunks = list(text_chunks)
                combined = " ".join(c.strip() for c in chunks if c and c.strip())
                provider = speak_realtime(combined) if combined else ""
            if provider:
                self.metrics.responses += 1
            return provider or ""
        except Exception as exc:
            logger.warning("speak_response_stream failed: %s", exc)
            return ""

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                partial = self._partial_q.get(timeout=0.1)
            except queue.Empty:
                continue
            self._process_partial(partial)

    def _process_partial(self, partial: str) -> None:
        t0 = time.perf_counter()
        self.metrics.partial_updates += 1
        if self.on_partial:
            try:
                self.on_partial(partial)
            except Exception as exc:
                logger.debug("on_partial failed: %s", exc)
        try:
            from conversation.semantic_stream.engine import on_partial_transcript

            on_partial_transcript(partial, session_context=self.session_context)
        except Exception:
            pass
        try:
            from brain.realtime_understanding import predict_intent, prepare_speculative_response

            prediction = predict_intent(partial, session_context=self.session_context)
            if prediction is not None:
                self.metrics.predictions += 1
                if self.on_prediction:
                    try:
                        self.on_prediction(prediction)
                    except Exception:
                        pass
                spec = prepare_speculative_response(partial, prediction)
                if spec.get("ready") and prediction.early_ack:
                    try:
                        from conversation.latency_hints import deliver_fast_ack

                        deliver_fast_ack(
                            prediction.early_ack,
                            input_mode="voice",
                            speak=False,
                            intent=prediction.intent,
                        )
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("prediction skipped: %s", exc)
        self.metrics.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        try:
            from ui.overlay_app import notify_overlay_conversation_stream

            notify_overlay_conversation_stream(
                partial=partial[:120],
                intent=getattr(prediction, "intent", "") if "prediction" in locals() and prediction else "",
            )
        except Exception:
            pass

    def run_continuous_session(
        self,
        *,
        listen_seconds: float = 30.0,
        audio_feed: Callable[[], Any] | None = None,
        on_final: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run a continuous conversational capture window."""
        from assistant.conversation_state import set_continuous_listening

        set_continuous_listening(True)
        self.start()
        result: dict[str, Any] = {"text": "", "partials": 0, "predictions": self.metrics.predictions}
        try:
            from voice.streaming_stt.stream_session import StreamingSttSession, is_streaming_stt_enabled

            if not is_streaming_stt_enabled():
                return {"error": "streaming STT disabled (stable mode or config)", **result}
            session = StreamingSttSession(
                session_context=self.session_context,
                audio_feed=audio_feed,
            )

            stt_result = session.run_until_endpoint(max_seconds=listen_seconds)
            result["text"] = stt_result.text
            result["partials"] = stt_result.partial_updates
            result["predictions"] = self.metrics.predictions
            result["prefetch_intent"] = stt_result.prefetch_intent
            if on_final and stt_result.text:
                on_final(stt_result.text)
        except Exception as exc:
            result["error"] = str(exc)
            logger.warning("continuous session failed: %s", exc)
        finally:
            set_continuous_listening(False)
        return result


_pipeline: StreamingPipeline | None = None
_pipeline_lock = threading.Lock()


def get_streaming_pipeline(*, session_context: object | None = None) -> StreamingPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            _pipeline = StreamingPipeline(session_context=session_context)
        elif session_context is not None:
            _pipeline.session_context = session_context
        return _pipeline


def reset_streaming_pipeline_for_tests() -> None:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            _pipeline.stop()
        _pipeline = None


def get_pipeline_metrics() -> dict[str, Any]:
    pipe = _pipeline
    if pipe is None:
        return {}
    m = pipe.metrics
    return {
        "partial_updates": m.partial_updates,
        "predictions": m.predictions,
        "interruptions": m.interruptions,
        "responses": m.responses,
        "last_latency_ms": round(m.last_latency_ms, 1),
    }


def show_realtime_runtime() -> str:
    from assistant.conversation_state import show_conversation_state
    from voice.interruption_manager import get_interruption_snapshot

    metrics = get_pipeline_metrics()
    intr = get_interruption_snapshot()
    lines = [
        "Real-time conversational runtime (Phase 56):",
        f"  partial updates: {metrics.get('partial_updates', 0)}",
        f"  predictions: {metrics.get('predictions', 0)}",
        f"  interruptions: {metrics.get('interruptions', 0)}",
        f"  responses: {metrics.get('responses', 0)}",
        f"  last partial latency ms: {metrics.get('last_latency_ms', 0)}",
        f"  interruption state: {intr.get('state', 'idle')}",
        f"  paused response chars: {intr.get('paused_response_chars', 0)}",
        "",
        show_conversation_state(),
    ]
    try:
        from voice.voice_latency_metrics import format_voice_latency_status

        lines.extend(["", format_voice_latency_status()])
    except Exception:
        pass
    return "\n".join(lines)


def phase56_status() -> str:
    from voice.backend_manager import show_backend_status

    lines = [
        "Phase 56 — Real-Time Conversational Runtime",
        show_realtime_runtime(),
        "",
        show_backend_status(),
    ]
    return "\n".join(lines)
