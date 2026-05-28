"""Natural turn-taking state during streaming conversation."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum

_lock = threading.Lock()
_state: "TurnStateMachine | None" = None


class TurnPhase(str, Enum):
    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    USER_PAUSE = "user_pause"
    USER_ENDPOINT = "user_endpoint"
    JARVIS_SPEAKING = "jarvis_speaking"
    USER_INTERRUPT = "user_interrupt"


@dataclass
class TurnStateMachine:
    phase: TurnPhase = TurnPhase.IDLE
    last_user_activity: float = 0.0
    last_partial_at: float = 0.0
    interrupt_count: int = 0

    def on_partial(self) -> None:
        now = time.monotonic()
        self.last_partial_at = now
        self.last_user_activity = now
        if self.phase in (TurnPhase.IDLE, TurnPhase.USER_PAUSE, TurnPhase.USER_ENDPOINT):
            self.phase = TurnPhase.USER_SPEAKING
        elif self.phase == TurnPhase.JARVIS_SPEAKING:
            self.phase = TurnPhase.USER_INTERRUPT
            self.interrupt_count += 1

    def on_endpoint(self) -> None:
        self.phase = TurnPhase.USER_ENDPOINT

    def on_jarvis_speak_start(self) -> None:
        self.phase = TurnPhase.JARVIS_SPEAKING

    def on_jarvis_speak_end(self) -> None:
        if self.phase == TurnPhase.JARVIS_SPEAKING:
            self.phase = TurnPhase.IDLE

    def on_pause(self, *, pause_ms: float) -> None:
        if self.phase == TurnPhase.USER_SPEAKING and pause_ms >= 300:
            self.phase = TurnPhase.USER_PAUSE


def get_turn_state() -> TurnStateMachine:
    global _state
    with _lock:
        if _state is None:
            _state = TurnStateMachine()
        return _state


def reset_turn_state() -> None:
    global _state
    with _lock:
        _state = TurnStateMachine()
