"""Lightweight local STT diagnostics (in-memory, display-only)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

_lock = Lock()
_stats = None


@dataclass
class SttDiagnosticsSnapshot:
    transcribe_count: int = 0
    transcribe_ms_total: float = 0.0
    low_confidence_count: int = 0
    empty_transcript_count: int = 0
    wake_retry_count: int = 0
    consecutive_empty_wake: int = 0
    empty_wake_guidance_count: int = 0
    last_model: str = ""
    last_engine: str = ""

    @property
    def avg_transcribe_ms(self) -> float | None:
        if self.transcribe_count <= 0:
            return None
        return self.transcribe_ms_total / self.transcribe_count


def _get_stats() -> SttDiagnosticsSnapshot:
    global _stats
    if _stats is None:
        _stats = SttDiagnosticsSnapshot()
    return _stats


def record_transcription(
    *,
    model: str,
    engine: str = "",
    duration_ms: float = 0.0,
    low_confidence: bool = False,
    empty: bool = False,
) -> None:
    with _lock:
        s = _get_stats()
        s.transcribe_count += 1
        s.transcribe_ms_total += max(0.0, float(duration_ms))
        if low_confidence:
            s.low_confidence_count += 1
        if empty:
            s.empty_transcript_count += 1
        else:
            s.consecutive_empty_wake = 0
        if model:
            s.last_model = model[:80]
        if engine:
            s.last_engine = engine[:40]


def record_wake_retry() -> None:
    with _lock:
        _get_stats().wake_retry_count += 1


def record_empty_wake_guidance() -> None:
    with _lock:
        s = _get_stats()
        s.consecutive_empty_wake += 1
        s.empty_wake_guidance_count += 1
        s.empty_transcript_count += 1


def reset_empty_wake_streak() -> None:
    with _lock:
        _get_stats().consecutive_empty_wake = 0


def snapshot() -> SttDiagnosticsSnapshot:
    with _lock:
        s = _get_stats()
        return SttDiagnosticsSnapshot(
            transcribe_count=s.transcribe_count,
            transcribe_ms_total=s.transcribe_ms_total,
            low_confidence_count=s.low_confidence_count,
            empty_transcript_count=s.empty_transcript_count,
            wake_retry_count=s.wake_retry_count,
            consecutive_empty_wake=s.consecutive_empty_wake,
            empty_wake_guidance_count=s.empty_wake_guidance_count,
            last_model=s.last_model,
            last_engine=s.last_engine,
        )


def format_diagnostics_lines() -> list[str]:
    s = snapshot()
    lines = [
        "STT diagnostics (session)",
        f"  avg_transcribe_ms: {s.avg_transcribe_ms:.0f}"
        if s.avg_transcribe_ms is not None
        else "  avg_transcribe_ms: n/a",
        f"  transcribe_count: {s.transcribe_count}",
        f"  low_confidence_count: {s.low_confidence_count}",
        f"  empty_transcript_count: {s.empty_transcript_count}",
        f"  wake_retries: {s.wake_retry_count}",
        f"  consecutive_empty_wake: {s.consecutive_empty_wake}",
        f"  empty_wake_guidance: {s.empty_wake_guidance_count}",
        f"  last_stt_model: {s.last_model or 'n/a'}",
    ]
    if s.last_engine:
        lines.append(f"  last_stt_engine: {s.last_engine}")
    return lines


def reset_stt_diagnostics() -> None:
    global _stats
    with _lock:
        _stats = SttDiagnosticsSnapshot()
