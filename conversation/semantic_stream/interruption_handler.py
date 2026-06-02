"""Conversational interruption — user speech during JARVIS TTS."""

from __future__ import annotations

from dataclasses import dataclass

import config as cfg
from conversation.semantic_stream.turn_taking import TurnPhase, get_turn_state


@dataclass(frozen=True)
class InterruptionEvent:
    detected: bool
    barge_in_triggered: bool
    turn_phase: str


def handle_streaming_interruption(*, speech_detected: bool) -> InterruptionEvent:
    """
    Coordinate barge-in with turn-taking. Does not execute commands.
    """
    if not cfg.CONV_INTERRUPTION_ENABLED:
        turn = get_turn_state()
        return InterruptionEvent(
            detected=False,
            barge_in_triggered=False,
            turn_phase=turn.phase.value,
        )
    turn = get_turn_state()
    barge = False
    if not speech_detected:
        return InterruptionEvent(
            detected=False,
            barge_in_triggered=False,
            turn_phase=turn.phase.value,
        )
    turn.on_partial()
    try:
        from config import TTS_BARGE_IN_ENABLED

        if TTS_BARGE_IN_ENABLED and turn.phase == TurnPhase.USER_INTERRUPT:
            from voice.human_conversation import (
                interrupt_on_user_speech_start,
                is_barge_in_active,
            )

            if not is_barge_in_active():
                barge = interrupt_on_user_speech_start()
            else:
                barge = True
    except Exception:
        pass
    return InterruptionEvent(
        detected=turn.phase == TurnPhase.USER_INTERRUPT,
        barge_in_triggered=barge,
        turn_phase=turn.phase.value,
    )
