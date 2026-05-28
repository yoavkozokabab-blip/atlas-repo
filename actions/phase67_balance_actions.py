"""Phase 67 balance actions — real voice test, desktop vision health."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


class TestRealVoiceConversationAction(BaseAction):
    intent = Intent.TEST_REAL_VOICE_CONVERSATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.real_voice_conversation import run_real_voice_conversation_test

        ok, body = run_real_voice_conversation_test()
        if not ok:
            return result_failed(Intent.TEST_REAL_VOICE_CONVERSATION, body)
        return result_success(Intent.TEST_REAL_VOICE_CONVERSATION, body)


class ShowDesktopVisionHealthAction(BaseAction):
    intent = Intent.SHOW_DESKTOP_VISION_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.desktop_vision_health import show_desktop_vision_health

        return result_success(
            Intent.SHOW_DESKTOP_VISION_HEALTH,
            show_desktop_vision_health(),
            data={"read_only": True},
        )
