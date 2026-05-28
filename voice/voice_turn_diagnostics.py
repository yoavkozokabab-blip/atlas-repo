"""Per-turn conversational voice diagnostics (Phase 60)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class VoiceTurnDiagnostics:
    speech_start_ts: float | None = None
    last_voice_ts: float | None = None
    silence_duration_s: float = 0.0
    endpoint_reason: str = ""
    tts_active_during_capture: bool = False
    chunk_energy: float = 0.0
    vad_probability: float = 0.0
    target_endpoint_min_s: float = 1.0
    target_endpoint_max_s: float = 1.8
    created_ts: float = field(default_factory=time.time)

    def format_status(self) -> str:
        lines = [
            "Voice turn diagnostics (Phase 60):",
            f"  speech_start_ts: {_fmt_ts(self.speech_start_ts)}",
            f"  last_voice_ts: {_fmt_ts(self.last_voice_ts)}",
            f"  silence_duration_s: {self.silence_duration_s:.3f}",
            f"  endpoint_reason: {self.endpoint_reason or 'n/a'}",
            f"  tts_active_during_capture: {'yes' if self.tts_active_during_capture else 'no'}",
            f"  chunk_energy: {self.chunk_energy:.6f}",
            f"  vad_probability: {self.vad_probability:.3f}",
            (
                f"  endpoint_target_s: {self.target_endpoint_min_s:.1f}-{self.target_endpoint_max_s:.1f} "
                f"({'PASS' if self.target_endpoint_min_s <= self.silence_duration_s <= self.target_endpoint_max_s else 'MISS'})"
            ),
        ]
        return "\n".join(lines)


_lock = threading.Lock()
_last = VoiceTurnDiagnostics()


def begin_turn() -> None:
    global _last
    with _lock:
        _last = VoiceTurnDiagnostics()


def note_chunk(*, energy: float, vad_probability: float, tts_active: bool) -> None:
    with _lock:
        _last.chunk_energy = max(0.0, float(energy))
        _last.vad_probability = max(0.0, min(1.0, float(vad_probability)))
        _last.tts_active_during_capture = _last.tts_active_during_capture or bool(tts_active)


def note_speech_detected() -> None:
    now = time.time()
    with _lock:
        if _last.speech_start_ts is None:
            _last.speech_start_ts = now
        _last.last_voice_ts = now
        _last.silence_duration_s = 0.0


def note_silence(*, silence_ms: float) -> None:
    with _lock:
        _last.silence_duration_s = max(0.0, float(silence_ms) / 1000.0)


def note_endpoint(reason: str) -> None:
    with _lock:
        _last.endpoint_reason = (reason or "unknown")[:120]


def get_last_voice_turn_diagnostics() -> VoiceTurnDiagnostics:
    with _lock:
        return VoiceTurnDiagnostics(**_last.__dict__)


def _fmt_ts(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"

