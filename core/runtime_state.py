"""In-process runtime flags (not persisted, no secrets)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class RuntimeState:
    """Volatile UI/runtime toggles for tray and voice modes."""

    voice_enabled: bool = False
    speak_enabled: bool = False
    tray_enabled: bool = False
    overlay_enabled: bool = False
    running: bool = True
    last_result_summary: str = ""
    last_error: str | None = None
    wake_word_enabled: bool = False
    wake_word_last_detected: str | None = None
    wake_word_last_score: float = 0.0
    wake_word_listening_active: bool = False
    wake_word_errors: int = 0
    wake_word_detection_count: int = 0
    wake_word_cooldown_until: float = 0.0
    wake_word_last_error: str | None = None
    version: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    runtime_counters: dict[str, int] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def set_voice(self, enabled: bool) -> None:
        with self._lock:
            self.voice_enabled = enabled
            self._touch_locked("voice")

    def set_speak(self, enabled: bool) -> None:
        with self._lock:
            self.speak_enabled = enabled
            self._touch_locked("speak")

    def set_wake_word(self, enabled: bool) -> None:
        with self._lock:
            self.wake_word_enabled = enabled
            self._touch_locked("wake_word")

    def set_overlay(self, enabled: bool) -> None:
        with self._lock:
            self.overlay_enabled = enabled
            self._touch_locked("overlay")

    def record_wake_detection(self, score: float) -> None:
        with self._lock:
            self.wake_word_last_score = float(score)
            self.wake_word_last_detected = datetime.now(timezone.utc).isoformat()
            self.wake_word_detection_count += 1
            self._touch_locked("wake_detection")

    def increment_wake_error(self, message: str | None = None) -> None:
        with self._lock:
            self.wake_word_errors += 1
            if message:
                self.wake_word_last_error = message[:200]
            self._touch_locked("wake_error")

    def acquire_wake_listening_session(self) -> bool:
        with self._lock:
            if self.wake_word_listening_active:
                return False
            self.wake_word_listening_active = True
            self._touch_locked("wake_session_acquired")
            return True

    def release_wake_listening_session(self) -> None:
        with self._lock:
            self.wake_word_listening_active = False
            self._touch_locked("wake_session_released")

    def start_wake_cooldown(self, seconds: float) -> float:
        with self._lock:
            delay = max(0.0, float(seconds))
            self.wake_word_cooldown_until = time.monotonic() + delay
            self._touch_locked("wake_cooldown")
            return self.wake_word_cooldown_until

    def record_result(self, summary: str, error: str | None = None) -> None:
        with self._lock:
            self.last_result_summary = (summary or "")[:500]
            self.last_error = (error[:200] if error else None)
            self._touch_locked("result")

    def stop(self) -> None:
        with self._lock:
            self.running = False
            self._touch_locked("stop")

    def increment_counter(self, name: str, amount: int = 1) -> int:
        with self._lock:
            current = self.runtime_counters.get(name, 0) + int(amount)
            self.runtime_counters[name] = current
            self._touch_locked(f"counter:{name}")
            return current

    def record_event(self, name: str, **payload: Any) -> None:
        safe_payload = {
            str(k): str(v)[:200]
            for k, v in payload.items()
            if k and v is not None
        }
        with self._lock:
            self.recent_events.append(
                {
                    "name": name[:80],
                    "at": datetime.now(timezone.utc).isoformat(),
                    "payload": safe_payload,
                }
            )
            if len(self.recent_events) > 50:
                del self.recent_events[: len(self.recent_events) - 50]
            self._touch_locked(f"event:{name}")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "voice_enabled": self.voice_enabled,
                "speak_enabled": self.speak_enabled,
                "tray_enabled": self.tray_enabled,
                "overlay_enabled": self.overlay_enabled,
                "running": self.running,
                "wake_word_enabled": self.wake_word_enabled,
                "wake_word_listening_active": self.wake_word_listening_active,
                "wake_word_detection_count": self.wake_word_detection_count,
                "wake_word_errors": self.wake_word_errors,
                "last_result_summary": self.last_result_summary,
                "last_error": self.last_error,
                "version": self.version,
                "updated_at": self.updated_at,
                "runtime_counters": dict(self.runtime_counters),
                "recent_events": list(self.recent_events[-10:]),
            }

    def _touch_locked(self, reason: str) -> None:
        self.version += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.runtime_counters["state_updates"] = self.runtime_counters.get("state_updates", 0) + 1


_state: RuntimeState | None = None


def get_runtime_state() -> RuntimeState:
    global _state
    if _state is None:
        _state = RuntimeState()
    return _state


def reset_runtime_state() -> None:
    global _state
    _state = None
