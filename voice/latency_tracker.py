"""Per-voice-command latency metrics (logging only)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.latency")

_lock = threading.Lock()
_current: "VoiceLatencyRecord | None" = None
_last: "VoiceLatencyRecord | None" = None


@dataclass
class VoiceLatencyRecord:
    source: str = "voice"
    wake_detect_ms: float | None = None
    first_partial_ms: float | None = None
    endpoint_ms: float | None = None
    record_ms: float | None = None
    transcribe_ms: float | None = None
    final_transcript_ms: float | None = None
    classify_ms: float | None = None
    execute_ms: float | None = None
    first_response_ms: float | None = None
    total_after_speech_end_ms: float | None = None
    tts_ms: float | None = None
    tts_note: str = ""
    total_ms: float | None = None
    transcript: str = ""
    intent: str = ""
    _started: float = field(default_factory=time.perf_counter, repr=False)
    _speech_end_perf: float | None = field(default=None, repr=False)

    def finish(self) -> None:
        if self.total_ms is None:
            self.total_ms = (time.perf_counter() - self._started) * 1000.0

    def as_log_line(self) -> str:
        parts = [
            f"source={self.source}",
            f"wake_detect_ms={self._fmt(self.wake_detect_ms)}",
            f"first_partial_ms={self._fmt(self.first_partial_ms)}",
            f"endpoint_ms={self._fmt(self.endpoint_ms)}",
            f"record_ms={self._fmt(self.record_ms)}",
            f"transcribe_ms={self._fmt(self.transcribe_ms)}",
            f"final_transcript_ms={self._fmt(self.final_transcript_ms)}",
            f"classify_ms={self._fmt(self.classify_ms)}",
            f"execute_ms={self._fmt(self.execute_ms)}",
            f"first_response_ms={self._fmt(self.first_response_ms)}",
            f"total_after_speech_end_ms={self._fmt(self.total_after_speech_end_ms)}",
            f"tts_ms={self._fmt(self.tts_ms)}",
            f"total_ms={self._fmt(self.total_ms)}",
        ]
        if self.tts_note:
            parts.append(f"tts_note={self.tts_note}")
        if self.intent:
            parts.append(f"intent={self.intent}")
        return "voice_latency " + " ".join(parts)

    @staticmethod
    def _fmt(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "-"

    def format_status(self) -> str:
        self.finish()
        lines = [
            "Voice latency (last command)",
            f"  wake_detect_ms: {self._fmt(self.wake_detect_ms)}",
            f"  first_partial_ms: {self._fmt(self.first_partial_ms)}",
            f"  endpoint_ms: {self._fmt(self.endpoint_ms)}",
            f"  record_ms: {self._fmt(self.record_ms)}",
            f"  transcribe_ms: {self._fmt(self.transcribe_ms)}",
            f"  final_transcript_ms: {self._fmt(self.final_transcript_ms)}",
            f"  classify_ms: {self._fmt(self.classify_ms)}",
            f"  execute_ms: {self._fmt(self.execute_ms)}",
            f"  first_response_ms: {self._fmt(self.first_response_ms)}",
            f"  total_after_speech_end_ms: {self._fmt(self.total_after_speech_end_ms)}",
            f"  tts_ms: {self._fmt(self.tts_ms)}",
            f"  tts_note: {self.tts_note or 'n/a'}",
            f"  total_ms: {self._fmt(self.total_ms)}",
        ]
        if self.transcript:
            lines.append(f"  transcript: {self.transcript[:80]!r}")
        if self.intent:
            lines.append(f"  intent: {self.intent}")
        return "\n".join(lines)

    def _target(self, name: str, value: float | None, limit_ms: float) -> str:
        if value is None:
            return f"  {name}: unknown (target <{limit_ms:.0f}ms)"
        state = "PASS" if value < limit_ms else "MISS"
        return f"  {name}: {state} ({self._fmt(value)}ms, target <{limit_ms:.0f}ms)"

    def _needs_speed_recommendations(self) -> bool:
        checks = (
            (self.first_partial_ms, 300.0),
            (self.final_transcript_ms, 500.0),
            (self.total_after_speech_end_ms, 500.0),
        )
        return any(value is None or value >= limit for value, limit in checks)

    def format_latency_budget(self) -> str:
        self.finish()
        lines = [
            "Voice latency budget (last command)",
            f"  wake_detect_ms: {self._fmt(self.wake_detect_ms)}",
            f"  first_partial_ms: {self._fmt(self.first_partial_ms)}",
            f"  endpoint_ms: {self._fmt(self.endpoint_ms)}",
            f"  final_transcript_ms: {self._fmt(self.final_transcript_ms)}",
            f"  classify_ms: {self._fmt(self.classify_ms)}",
            f"  first_response_ms: {self._fmt(self.first_response_ms)}",
            f"  total_after_speech_end_ms: {self._fmt(self.total_after_speech_end_ms)}",
            "Targets",
            self._target("first partial", self.first_partial_ms, 300.0),
            self._target("final transcript after speech end", self.final_transcript_ms, 500.0),
            self._target("first response after speech end", self.total_after_speech_end_ms, 500.0),
        ]
        if self.intent:
            lines.append(f"  intent: {self.intent}")
        if self._needs_speed_recommendations():
            lines.extend(
                [
                    "Recommended if CPU cannot hit target",
                    "  STT_MODEL=tiny",
                    "  STT_STREAM_ENDPOINT_SILENCE_MS=350",
                    "  CONVERSATION_SEMANTIC_STREAM_ENABLED=false",
                    "  use fast lane only for common commands",
                ]
            )
        return "\n".join(lines)


def begin_voice_command(*, source: str = "voice") -> VoiceLatencyRecord:
    global _current
    rec = VoiceLatencyRecord(source=source)
    with _lock:
        _current = rec
    return rec


def get_current_latency() -> VoiceLatencyRecord | None:
    with _lock:
        return _current


def mark_wake_detected(ms: float | None = None) -> None:
    with _lock:
        if _current is None:
            return
        if ms is not None:
            _current.wake_detect_ms = ms
        elif _current.wake_detect_ms is None:
            _current.wake_detect_ms = 0.0


def mark_first_partial(ms: float | None = None) -> None:
    with _lock:
        if _current is None or _current.first_partial_ms is not None:
            return
        _current.first_partial_ms = (
            ms if ms is not None else (time.perf_counter() - _current._started) * 1000.0
        )


def mark_endpoint(ms: float | None = None) -> None:
    with _lock:
        if _current is None or _current.endpoint_ms is not None:
            return
        _current.endpoint_ms = (
            ms if ms is not None else (time.perf_counter() - _current._started) * 1000.0
        )
        _current._speech_end_perf = time.perf_counter()


def set_record_ms(ms: float) -> None:
    with _lock:
        if _current is not None:
            _current.record_ms = ms


def set_transcribe_ms(ms: float) -> None:
    with _lock:
        if _current is not None:
            _current.transcribe_ms = ms


def set_final_transcript_ms(ms: float) -> None:
    with _lock:
        if _current is not None:
            _current.final_transcript_ms = ms


def set_route_timing(*, classify_ms: float, execute_ms: float, intent: str = "") -> None:
    with _lock:
        if _current is not None:
            _current.classify_ms = classify_ms
            _current.execute_ms = execute_ms
            if intent:
                _current.intent = intent


def mark_first_response(ms: float | None = None) -> None:
    with _lock:
        if _current is None or _current.first_response_ms is not None:
            return
        now = time.perf_counter()
        _current.first_response_ms = (
            ms if ms is not None else (now - _current._started) * 1000.0
        )
        if _current._speech_end_perf is not None:
            _current.total_after_speech_end_ms = (now - _current._speech_end_perf) * 1000.0


def _apply_tts_timing(*, ms: float | None, note: str = "") -> None:
    with _lock:
        for rec in (_current, _last):
            if rec is None:
                continue
            if ms is not None:
                rec.tts_ms = ms
            if note:
                rec.tts_note = note[:120]


def set_tts_ms(ms: float) -> None:
    _apply_tts_timing(ms=ms)


def mark_tts_pending() -> None:
    _apply_tts_timing(ms=0.0, note="async_pending")


def mark_tts_skipped(reason: str) -> None:
    _apply_tts_timing(ms=0.0, note=f"skipped:{reason}")


def mark_tts_failed(reason: str) -> None:
    _apply_tts_timing(ms=0.0, note=f"failed:{reason[:80]}")


def set_transcript(text: str) -> None:
    with _lock:
        if _current is not None:
            _current.transcript = (text or "")[:200]


def finish_and_log(*, wait_for_tts: bool = False, tts_wait_seconds: float = 12.0) -> VoiceLatencyRecord | None:
    global _current, _last
    try:
        from core.test_runtime import is_test_mode

        if is_test_mode():
            wait_for_tts = False
            tts_wait_seconds = min(tts_wait_seconds, 0.25)
    except Exception:
        pass
    if wait_for_tts and tts_wait_seconds > 0:
        deadline = time.perf_counter() + tts_wait_seconds
        while time.perf_counter() < deadline:
            with _lock:
                rec = _current
                if rec is None:
                    break
                if rec.tts_ms is not None and (
                    rec.tts_ms > 0 or rec.tts_note.startswith(("failed:", "skipped:"))
                ):
                    break
            time.sleep(0.05)

    with _lock:
        rec = _current
        if rec is None:
            return _last
        rec.finish()
        _last = rec
        _current = None
    logger.info(rec.as_log_line())
    print(rec.as_log_line(), flush=True)
    try:
        from services.observability import get_observability

        obs = get_observability()
        if rec.total_ms is not None:
            obs.record_latency("voice.total", rec.total_ms, source=rec.source, intent=rec.intent)
        for name, value in (
            ("voice.record", rec.record_ms),
            ("voice.first_partial", rec.first_partial_ms),
            ("voice.endpoint", rec.endpoint_ms),
            ("voice.stt", rec.transcribe_ms),
            ("voice.final_transcript", rec.final_transcript_ms),
            ("voice.classify", rec.classify_ms),
            ("voice.execute", rec.execute_ms),
            ("voice.first_response", rec.first_response_ms),
            ("voice.after_speech_end", rec.total_after_speech_end_ms),
            ("voice.tts", rec.tts_ms),
        ):
            if value is not None:
                obs.record_latency(name, value, source=rec.source, intent=rec.intent)
    except Exception:
        pass
    return rec


def get_last_latency() -> VoiceLatencyRecord | None:
    with _lock:
        return _last


def reset_latency_tracker() -> None:
    global _current, _last
    with _lock:
        _current = None
        _last = None
