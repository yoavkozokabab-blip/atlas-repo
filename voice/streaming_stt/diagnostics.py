"""Streaming STT timing diagnostics (Phase 59.6)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()
_diag: "StreamingSttDiagnostics | None" = None


@dataclass
class StreamingSttDiagnostics:
    session_started_mono: float = 0.0
    mic_opened: bool = False
    mic_open_ms: float | None = None
    thread_started: bool = False
    thread_start_ms: float | None = None
    audio_frames_received: bool = False
    first_chunk_ms: float | None = None
    chunks_received: int = 0
    bytes_received: int = 0
    dropped_chunks: int = 0
    queue_backlog: int = 0
    vad_speech_started: bool = False
    vad_start_ms: float | None = None
    first_partial_ms: float | None = None
    first_partial_text: str = ""
    inference_start_ms: float | None = None
    inference_end_ms: float | None = None
    last_inference_ms: float = 0.0
    partial_attempts: int = 0
    partial_timeouts: int = 0
    partial_retries: int = 0
    stream_queue_wait_ms: float = 0.0
    cpu_overload_suspected: bool = False
    streaming_disabled: bool = False
    disable_reason: str = ""
    stream_alive: bool = True

    def _elapsed_ms(self, mono: float | None) -> float | None:
        if mono is None or self.session_started_mono <= 0:
            return None
        return (mono - self.session_started_mono) * 1000.0

    def as_report_lines(self) -> list[str]:
        lines = [
            "Streaming STT diagnostics (Phase 59.6):",
            f"  mic opened: {'yes' if self.mic_opened else 'no'}"
            + (f" ({self.mic_open_ms:.0f} ms)" if self.mic_open_ms is not None else ""),
            f"  worker thread started: {'yes' if self.thread_started else 'no'}"
            + (f" ({self.thread_start_ms:.0f} ms)" if self.thread_start_ms is not None else ""),
            f"  audio frames received: {'yes' if self.audio_frames_received else 'no'}"
            + (f" (first {self.first_chunk_ms:.0f} ms)" if self.first_chunk_ms is not None else ""),
            f"  chunks received: {self.chunks_received}",
            f"  bytes received: {self.bytes_received}",
            f"  dropped chunks: {self.dropped_chunks}",
            f"  queue backlog: {self.queue_backlog}",
            f"  VAD speech started: {'yes' if self.vad_speech_started else 'no'}"
            + (f" ({self.vad_start_ms:.0f} ms)" if self.vad_start_ms is not None else ""),
            f"  first partial token: {'yes' if self.first_partial_ms is not None else 'no'}"
            + (
                f" ({self.first_partial_ms:.0f} ms) text={self.first_partial_text[:60]!r}"
                if self.first_partial_ms is not None
                else ""
            ),
            f"  inference last ms: {self.last_inference_ms:.0f}",
            f"  partial attempts: {self.partial_attempts}",
            f"  partial timeouts: {self.partial_timeouts}",
            f"  partial retries: {self.partial_retries}",
            f"  stream queue wait ms: {self.stream_queue_wait_ms:.0f}",
            f"  CPU overload suspected: {'yes' if self.cpu_overload_suspected else 'no'}",
            f"  stream alive: {'yes' if self.stream_alive else 'no'}",
            f"  streaming disabled: {'yes' if self.streaming_disabled else 'no'}",
        ]
        if self.disable_reason:
            lines.append(f"  disable reason: {self.disable_reason}")
        return lines


def _now_ms() -> float:
    diag = _diag
    if diag is None or diag.session_started_mono <= 0:
        return 0.0
    return (time.monotonic() - diag.session_started_mono) * 1000.0


def begin_streaming_diagnostics() -> StreamingSttDiagnostics:
    global _diag
    with _lock:
        _diag = StreamingSttDiagnostics(session_started_mono=time.monotonic())
        return _diag


def get_streaming_diagnostics() -> StreamingSttDiagnostics | None:
    with _lock:
        return _diag


def reset_streaming_diagnostics_for_tests() -> None:
    global _diag
    with _lock:
        _diag = None


def mark_thread_started() -> None:
    with _lock:
        if _diag is None:
            return
        if not _diag.thread_started:
            _diag.thread_started = True
            _diag.thread_start_ms = _now_ms()


def mark_mic_opened() -> None:
    with _lock:
        if _diag is None:
            return
        if not _diag.mic_opened:
            _diag.mic_opened = True
            _diag.mic_open_ms = _now_ms()


def mark_audio_chunk(samples: int, *, queue_backlog: int = 0) -> None:
    with _lock:
        if _diag is None:
            return
        _diag.chunks_received += 1
        _diag.bytes_received += max(0, int(samples)) * 4
        _diag.queue_backlog = max(0, int(queue_backlog))
        if not _diag.audio_frames_received:
            _diag.audio_frames_received = True
            _diag.first_chunk_ms = _now_ms()
        elif _diag.chunks_received > 2:
            # Gap between chunks > 3x expected chunk period suggests overload.
            pass


def mark_chunk_gap_overload(gap_ms: float, *, expected_ms: float) -> None:
    if gap_ms <= expected_ms * 3.0:
        return
    with _lock:
        if _diag is None:
            return
        _diag.cpu_overload_suspected = True
        _diag.dropped_chunks += 1


def mark_vad_speech_started() -> None:
    with _lock:
        if _diag is None:
            return
        if not _diag.vad_speech_started:
            _diag.vad_speech_started = True
            _diag.vad_start_ms = _now_ms()


def mark_inference_start() -> None:
    with _lock:
        if _diag is None:
            return
        if _diag.inference_start_ms is None:
            _diag.inference_start_ms = _now_ms()


def mark_inference_end(duration_ms: float) -> None:
    with _lock:
        if _diag is None:
            return
        _diag.inference_end_ms = _now_ms()
        _diag.last_inference_ms = max(0.0, float(duration_ms))


def mark_first_partial(text: str) -> None:
    with _lock:
        if _diag is None:
            return
        if _diag.first_partial_ms is None:
            _diag.first_partial_ms = _now_ms()
            _diag.first_partial_text = (text or "")[:120]


def mark_partial_attempt() -> None:
    with _lock:
        if _diag is None:
            return
        _diag.partial_attempts += 1


def mark_partial_timeout() -> None:
    with _lock:
        if _diag is None:
            return
        _diag.partial_timeouts += 1


def mark_partial_retry() -> None:
    with _lock:
        if _diag is None:
            return
        _diag.partial_retries += 1


def mark_stream_queue_wait(wait_ms: float) -> None:
    with _lock:
        if _diag is None:
            return
        _diag.stream_queue_wait_ms = max(_diag.stream_queue_wait_ms, float(wait_ms))


def mark_stream_disabled(reason: str) -> None:
    with _lock:
        if _diag is None:
            return
        _diag.streaming_disabled = True
        _diag.stream_alive = False
        _diag.disable_reason = (reason or "")[:200]


def mark_stream_alive(alive: bool) -> None:
    with _lock:
        if _diag is None:
            return
        _diag.stream_alive = alive


def format_streaming_diagnostics() -> str:
    with _lock:
        diag = _diag
    if diag is None:
        return "Streaming STT diagnostics: n/a (no active session)"
    return "\n".join(diag.as_report_lines())
