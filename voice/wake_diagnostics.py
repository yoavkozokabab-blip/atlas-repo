"""Wake-session capture diagnostics (in-memory, display-only)."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

_lock = Lock()


@dataclass
class WakeDiagnosticsSnapshot:
    wake_detected_count: int = 0
    session_count: int = 0
    session_ms_total: float = 0.0
    speech_ms_total: float = 0.0
    silence_cutoff_ms_total: float = 0.0
    stt_ms_total: float = 0.0
    clipped_session_count: int = 0
    empty_after_wake_count: int = 0
    false_trigger_cooldown_count: int = 0
    last_wake_raw_transcript: str = ""
    last_wake_normalized_transcript: str = ""
    last_wake_corrected_transcript: str = ""

    @property
    def avg_session_ms(self) -> float | None:
        if self.session_count <= 0:
            return None
        return self.session_ms_total / self.session_count

    @property
    def avg_speech_ms(self) -> float | None:
        if self.session_count <= 0:
            return None
        return self.speech_ms_total / self.session_count

    @property
    def avg_silence_cutoff_ms(self) -> float | None:
        if self.session_count <= 0:
            return None
        return self.silence_cutoff_ms_total / self.session_count

    @property
    def avg_stt_ms(self) -> float | None:
        if self.session_count <= 0:
            return None
        return self.stt_ms_total / self.session_count


_stats = WakeDiagnosticsSnapshot()


def record_wake_detected() -> None:
    with _lock:
        _stats.wake_detected_count += 1


def record_false_trigger_cooldown() -> None:
    with _lock:
        _stats.false_trigger_cooldown_count += 1


def record_wake_session(
    *,
    session_ms: float,
    speech_ms: float,
    silence_cutoff_ms: float,
    stt_ms: float = 0.0,
    empty_after_wake: bool,
    clipped: bool,
    raw_transcript: str = "",
    normalized_transcript: str = "",
    corrected_transcript: str = "",
) -> None:
    with _lock:
        _stats.session_count += 1
        _stats.session_ms_total += max(0.0, session_ms)
        _stats.speech_ms_total += max(0.0, speech_ms)
        _stats.silence_cutoff_ms_total += max(0.0, silence_cutoff_ms)
        _stats.stt_ms_total += max(0.0, stt_ms)
        if empty_after_wake:
            _stats.empty_after_wake_count += 1
        if clipped:
            _stats.clipped_session_count += 1
        if raw_transcript:
            _stats.last_wake_raw_transcript = raw_transcript[:500]
        if normalized_transcript:
            _stats.last_wake_normalized_transcript = normalized_transcript[:500]
        if corrected_transcript or normalized_transcript:
            _stats.last_wake_corrected_transcript = (corrected_transcript or normalized_transcript)[
                :500
            ]


def estimate_clipped_session(
    *,
    raw_text: str,
    normalized_text: str,
    speech_ms: float,
    empty_after_wake: bool,
    min_command_speech_ms: float,
) -> bool:
    if empty_after_wake:
        return True
    if speech_ms > 0 and speech_ms < min_command_speech_ms:
        return True
    norm = (normalized_text or "").strip().lower()
    raw = (raw_text or "").strip().lower()
    if not norm and raw:
        return True
    wake_only = norm in {"", "jarvis", "hey jarvis", "hi jarvis", "ok jarvis"}
    if wake_only and raw:
        return True
    return False


def snapshot() -> WakeDiagnosticsSnapshot:
    with _lock:
        s = _stats
        return WakeDiagnosticsSnapshot(
            wake_detected_count=s.wake_detected_count,
            session_count=s.session_count,
            session_ms_total=s.session_ms_total,
            speech_ms_total=s.speech_ms_total,
            silence_cutoff_ms_total=s.silence_cutoff_ms_total,
            stt_ms_total=s.stt_ms_total,
            clipped_session_count=s.clipped_session_count,
            empty_after_wake_count=s.empty_after_wake_count,
            false_trigger_cooldown_count=s.false_trigger_cooldown_count,
            last_wake_raw_transcript=s.last_wake_raw_transcript,
            last_wake_normalized_transcript=s.last_wake_normalized_transcript,
            last_wake_corrected_transcript=s.last_wake_corrected_transcript,
        )


def format_wake_diagnostics() -> str:
    s = snapshot()
    lines = [
        "Wake diagnostics",
        f"  wake_detected_count: {s.wake_detected_count}",
        f"  false_trigger_cooldown_count: {s.false_trigger_cooldown_count}",
        f"  wake_sessions: {s.session_count}",
        f"  avg_wake_session_ms: {s.avg_session_ms:.0f}"
        if s.avg_session_ms is not None
        else "  avg_wake_session_ms: n/a",
        f"  avg_speech_ms: {s.avg_speech_ms:.0f}"
        if s.avg_speech_ms is not None
        else "  avg_speech_ms: n/a",
        f"  avg_stt_ms: {s.avg_stt_ms:.0f}" if s.avg_stt_ms is not None else "  avg_stt_ms: n/a",
        f"  avg_silence_cutoff_ms: {s.avg_silence_cutoff_ms:.0f}"
        if s.avg_silence_cutoff_ms is not None
        else "  avg_silence_cutoff_ms: n/a",
        f"  clipped_session_estimate: {s.clipped_session_count}",
        f"  empty_after_wake_count: {s.empty_after_wake_count}",
        f"  last_wake_raw: {s.last_wake_raw_transcript!r}"
        if s.last_wake_raw_transcript
        else "  last_wake_raw: (none)",
        f"  last_wake_normalized: {s.last_wake_normalized_transcript!r}"
        if s.last_wake_normalized_transcript
        else "  last_wake_normalized: (none)",
        f"  last_wake_corrected: {s.last_wake_corrected_transcript!r}"
        if s.last_wake_corrected_transcript
        else "  last_wake_corrected: (none)",
    ]
    return "\n".join(lines)


def reset_wake_diagnostics() -> None:
    global _stats
    with _lock:
        _stats = WakeDiagnosticsSnapshot()
