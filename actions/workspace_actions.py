"""Phase 40a — workspace awareness (read-only)."""

from __future__ import annotations

from actions.base import BaseAction
from config import WORKSPACE_AWARENESS_ENABLED
from core.results import result_failed, result_success
from core.session import SessionState
from core.types import CommandRequest, CommandResult, Intent
from operating.workspace_context import (
    build_activity_snapshot,
    format_activity_report,
    persist_workspace_context,
)


class WhatAmIDoingAction(BaseAction):
    intent = Intent.WHAT_AM_I_DOING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not WORKSPACE_AWARENESS_ENABLED:
            return result_failed(
                Intent.WHAT_AM_I_DOING,
                "Workspace awareness is disabled. Set WORKSPACE_AWARENESS_ENABLED=true.",
            )
        session = SessionState.load()
        snap = build_activity_snapshot(session)
        persist_workspace_context(snap)
        session.activity_mode = snap.mode
        session.last_workspace_snapshot = snap.summary[:200]
        session.save()
        report = format_activity_report(snap)
        return result_success(
            Intent.WHAT_AM_I_DOING,
            report,
            data={
                "mode": snap.mode,
                "active_app": snap.active_app,
                "window_title": snap.window_title,
                "project_root": snap.project_root,
            },
            next_suggestions=snap.suggestions[:4],
        )
