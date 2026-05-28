"""Voice latency diagnostics (read-only)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.latency_tracker import get_last_latency
from voice.voice_turn_diagnostics import get_last_voice_turn_diagnostics


class ShowLatencyStatusAction(BaseAction):
    intent = Intent.SHOW_LATENCY_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        rec = get_last_latency()
        if rec is None:
            summary = (
                "No voice latency recorded yet. "
                "Use wake word or push-to-talk, then ask again."
            )
        elif request.params.get("budget") or "budget" in (request.raw_text or "").lower():
            summary = rec.format_latency_budget()
        else:
            turn = get_last_voice_turn_diagnostics()
            summary = f"{rec.format_status()}\n\n{turn.format_status()}"
        return result_success(Intent.SHOW_LATENCY_STATUS, summary)
