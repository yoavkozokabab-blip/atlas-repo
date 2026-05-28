"""Voice performance config display (read-only)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.performance_status import format_voice_performance_status


class ShowVoicePerformanceStatusAction(BaseAction):
    intent = Intent.SHOW_VOICE_PERFORMANCE_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SHOW_VOICE_PERFORMANCE_STATUS,
            format_voice_performance_status(),
        )
