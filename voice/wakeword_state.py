"""Wake word runtime state (volatile, not persisted)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime_state import RuntimeState


@dataclass
class WakeWordState:
    """In-memory wake word detector status."""

    enabled: bool = False
    actively_listening: bool = False
    last_detected_at: str | None = None
    last_score: float = 0.0
    detection_count: int = 0
    error_count: int = 0
    cooldown_until: float = 0.0
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "actively_listening": self.actively_listening,
            "last_detected_at": self.last_detected_at,
            "last_score": self.last_score,
            "detection_count": self.detection_count,
            "error_count": self.error_count,
            "cooldown_until": self.cooldown_until,
            "last_error": self.last_error,
        }


_lock = Lock()


def snapshot_from_runtime(runtime: "RuntimeState") -> WakeWordState:
    with _lock:
        return WakeWordState(
            enabled=runtime.wake_word_enabled,
            actively_listening=runtime.wake_word_listening_active,
            last_detected_at=runtime.wake_word_last_detected,
            last_score=runtime.wake_word_last_score,
            detection_count=runtime.wake_word_detection_count,
            error_count=runtime.wake_word_errors,
            cooldown_until=runtime.wake_word_cooldown_until,
            last_error=runtime.wake_word_last_error,
        )


def format_status(runtime: "RuntimeState") -> str:
    from voice.wakeword import format_wake_word_model_status, resolve_wake_word_model

    s = snapshot_from_runtime(runtime)
    lines = [
        f"Wake word enabled: {s.enabled}",
        f"Listening session active: {s.actively_listening}",
        f"Detections: {s.detection_count}",
        f"Last score: {s.last_score:.3f}" if s.last_score else "Last score: —",
        f"Last detected: {s.last_detected_at or 'never'}",
        f"Errors: {s.error_count}",
    ]
    if s.last_error:
        lines.append(f"Last error: {s.last_error[:120]}")
    lines.append("")
    lines.append(format_wake_word_model_status(resolve_wake_word_model()))
    return "\n".join(lines)
