"""Phase 40e — session memory intents."""

from __future__ import annotations

from actions.base import BaseAction
from config import SESSION_MEMORY_ENABLED
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from memory.session_memory import restore_context, summarize_session


class WhatWereWeDoingAction(BaseAction):
    intent = Intent.WHAT_WERE_WE_DOING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not SESSION_MEMORY_ENABLED:
            return result_failed(
                Intent.WHAT_WERE_WE_DOING,
                "Session memory disabled. Set SESSION_MEMORY_ENABLED=true.",
            )
        text = restore_context()
        return result_success(
            Intent.WHAT_WERE_WE_DOING,
            text,
            next_suggestions=["summarize session", "what am i doing", "show task status"],
        )


class SummarizeSessionAction(BaseAction):
    intent = Intent.SUMMARIZE_SESSION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not SESSION_MEMORY_ENABLED:
            return result_failed(
                Intent.SUMMARIZE_SESSION,
                "Session memory disabled. Set SESSION_MEMORY_ENABLED=true.",
            )
        text = summarize_session()
        return result_success(
            Intent.SUMMARIZE_SESSION,
            text,
            next_suggestions=["what were we doing", "show recent commands", "run diagnostics"],
        )
