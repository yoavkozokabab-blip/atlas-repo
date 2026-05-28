"""Phase 57/58 realtime TTS latency metrics with breakdown."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()
_last: "RealtimeVoiceLatency | None" = None
_history: list["RealtimeVoiceLatency"] = []


@dataclass
class RealtimeVoiceLatency:
    provider: str = ""
    time_to_first_audio_ms: float | None = None
    total_playback_ms: float | None = None
    interruption_latency_ms: float | None = None
    provider_latency_ms: float | None = None
    queue_wait_ms: float | None = None
    failover_from: str = ""
    cancelled: bool = False
    text_preview: str = ""
    provider_connect_ms: float | None = None
    first_byte_ms: float | None = None
    first_decodable_audio_ms: float | None = None
    playback_start_ms: float | None = None
    interruption_cancel_ms: float | None = None
    adaptive_buffer_bytes: int = 0
    _started: float = field(default_factory=time.perf_counter, repr=False)
    _first_audio: float | None = field(default=None, repr=False)
    _interrupt_t0: float | None = field(default=None, repr=False)
    _cancel_started: float | None = field(default=None, repr=False)

    def mark_first_byte(self) -> None:
        if self.first_byte_ms is None:
            self.first_byte_ms = (time.perf_counter() - self._started) * 1000.0

    def mark_first_decodable(self) -> None:
        if self.first_decodable_audio_ms is None:
            self.first_decodable_audio_ms = (time.perf_counter() - self._started) * 1000.0

    def mark_first_audio(self) -> None:
        if self._first_audio is None:
            self._first_audio = time.perf_counter()
            self.playback_start_ms = (self._first_audio - self._started) * 1000.0
            self.time_to_first_audio_ms = self.playback_start_ms

    def finish(self, *, cancelled: bool = False) -> None:
        self.cancelled = cancelled
        self.total_playback_ms = (time.perf_counter() - self._started) * 1000.0

    def mark_interrupt_begin(self) -> None:
        self._cancel_started = time.perf_counter()
        self._interrupt_t0 = self._cancel_started

    def mark_interrupt(self) -> None:
        if self._cancel_started is not None:
            self.interruption_cancel_ms = (time.perf_counter() - self._cancel_started) * 1000.0
        self._interrupt_t0 = time.perf_counter()
        if self._first_audio is not None:
            self.interruption_latency_ms = (self._interrupt_t0 - self._first_audio) * 1000.0


def begin_realtime_latency(*, provider: str, text: str = "") -> RealtimeVoiceLatency:
    global _last
    rec = RealtimeVoiceLatency(
        provider=provider,
        text_preview=(text or "")[:80],
    )
    with _lock:
        _last = rec
    return rec


def get_last_realtime_latency() -> RealtimeVoiceLatency | None:
    with _lock:
        return _last


def record_realtime_latency(rec: RealtimeVoiceLatency) -> None:
    global _last, _history
    with _lock:
        _last = rec
        _history.append(rec)
        if len(_history) > 20:
            _history = _history[-20:]


def reset_realtime_latency_for_tests() -> None:
    global _last, _history
    with _lock:
        _last = None
        _history = []


def format_voice_latency_status() -> str:
    with _lock:
        rec = _last
        hist = list(_history[-5:])
    lines = [
        "Voice latency (Phase 58 realtime TTS)",
        f"  provider: {rec.provider if rec else 'n/a'}",
        f"  time_to_first_audio_ms: {_fmt(rec.time_to_first_audio_ms if rec else None)}",
        f"  playback_start_ms: {_fmt(rec.playback_start_ms if rec else None)}",
        f"  total_speech_ms: {_fmt(rec.total_playback_ms if rec else None)}",
        f"  interruption_cancel_ms: {_fmt(rec.interruption_cancel_ms if rec else None)}",
        f"  provider_latency_ms: {_fmt(rec.provider_latency_ms if rec else None)}",
        f"  cancelled: {'yes' if rec and rec.cancelled else 'no' if rec else 'n/a'}",
    ]
    if rec and rec.text_preview:
        lines.append(f"  last text: {rec.text_preview!r}")
    if hist:
        lines.append("  recent:")
        for item in hist:
            lines.append(
                f"    - {item.provider}: ttf={_fmt(item.time_to_first_audio_ms)} "
                f"total={_fmt(item.total_playback_ms)}"
            )
    try:
        from voice.voice_turn_diagnostics import get_last_voice_turn_diagnostics

        lines.extend(["", get_last_voice_turn_diagnostics().format_status()])
    except Exception:
        pass
    return "\n".join(lines)


def format_realtime_latency_breakdown() -> str:
    with _lock:
        rec = _last
    lines = [
        "Realtime latency breakdown (Phase 58):",
        f"  provider: {rec.provider if rec else 'n/a'}",
        f"  provider_connect_ms: {_fmt(rec.provider_connect_ms if rec else None)}",
        f"  first_byte_ms: {_fmt(rec.first_byte_ms if rec else None)}",
        f"  first_decodable_audio_ms: {_fmt(rec.first_decodable_audio_ms if rec else None)}",
        f"  playback_start_ms: {_fmt(rec.playback_start_ms if rec else None)}",
        f"  time_to_first_audio_ms: {_fmt(rec.time_to_first_audio_ms if rec else None)}",
        f"  interruption_cancel_ms: {_fmt(rec.interruption_cancel_ms if rec else None)}",
        f"  provider_latency_ms: {_fmt(rec.provider_latency_ms if rec else None)}",
        f"  queue_wait_ms: {_fmt(rec.queue_wait_ms if rec else None)}",
        f"  adaptive_buffer_bytes: {rec.adaptive_buffer_bytes if rec else 'n/a'}",
        f"  total_playback_ms: {_fmt(rec.total_playback_ms if rec else None)}",
    ]
    if rec and rec.text_preview:
        lines.append(f"  last text: {rec.text_preview!r}")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "n/a"
