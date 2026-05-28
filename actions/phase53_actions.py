"""Phase 53 persistent assistant actions."""

from __future__ import annotations

from actions.base import BaseAction
from assistant.continuity_engine import (
    continue_previous_session,
    resume_latest_investigation,
    summarize_unresolved_issues,
    what_changed_since_last_session,
)
from assistant.intelligence_summary import (
    explain_current_operational_state,
    recommend_next_action,
    summarize_system_intelligence,
    summarize_unresolved_blockers,
    what_should_we_investigate_next,
)
from assistant.notifications import archive_notification, explain_notification
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from runtime.background_tasks import get_engine


class ReopenTaskResultAction(BaseAction):
    intent = Intent.REOPEN_TASK_RESULT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw_id = request.params.get("task_id")
        if raw_id is None:
            return result_failed(Intent.REOPEN_TASK_RESULT, "Specify task id: reopen task result 7")
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            return result_failed(Intent.REOPEN_TASK_RESULT, f"Invalid task id: {raw_id!r}")
        body = get_engine().reopen_task_result(task_id)
        return result_success(Intent.REOPEN_TASK_RESULT, body, data={"task_id": task_id, "read_only": True})


class ArchiveNotificationAction(BaseAction):
    intent = Intent.ARCHIVE_NOTIFICATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw_id = request.params.get("notification_id")
        if raw_id is None:
            return result_failed(Intent.ARCHIVE_NOTIFICATION, "Specify id: archive notification 4")
        try:
            note_id = int(raw_id)
        except (TypeError, ValueError):
            return result_failed(Intent.ARCHIVE_NOTIFICATION, f"Invalid notification id: {raw_id!r}")
        body = archive_notification(note_id)
        if body.startswith("No notification"):
            return result_failed(Intent.ARCHIVE_NOTIFICATION, body)
        return result_success(Intent.ARCHIVE_NOTIFICATION, body, data={"notification_id": note_id})


class ExplainNotificationAction(BaseAction):
    intent = Intent.EXPLAIN_NOTIFICATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw_id = request.params.get("notification_id")
        if raw_id is None:
            return result_failed(Intent.EXPLAIN_NOTIFICATION, "Specify id: explain notification 2")
        try:
            note_id = int(raw_id)
        except (TypeError, ValueError):
            return result_failed(Intent.EXPLAIN_NOTIFICATION, f"Invalid notification id: {raw_id!r}")
        body = explain_notification(note_id)
        if body.startswith("No notification"):
            return result_failed(Intent.EXPLAIN_NOTIFICATION, body)
        return result_success(Intent.EXPLAIN_NOTIFICATION, body, data={"read_only": True})


class ContinuePreviousSessionAction(BaseAction):
    intent = Intent.CONTINUE_PREVIOUS_SESSION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.CONTINUE_PREVIOUS_SESSION,
            continue_previous_session(),
            data={"read_only": True},
        )


class SummarizeUnresolvedIssuesAction(BaseAction):
    intent = Intent.SUMMARIZE_UNRESOLVED_ISSUES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SUMMARIZE_UNRESOLVED_ISSUES,
            summarize_unresolved_issues(),
            data={"read_only": True},
        )


class ResumeLatestInvestigationAction(BaseAction):
    intent = Intent.RESUME_LATEST_INVESTIGATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.RESUME_LATEST_INVESTIGATION,
            resume_latest_investigation(),
            data={"read_only": True},
        )


class WhatChangedSinceLastSessionAction(BaseAction):
    intent = Intent.WHAT_CHANGED_SINCE_LAST_SESSION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.WHAT_CHANGED_SINCE_LAST_SESSION,
            what_changed_since_last_session(),
            data={"read_only": True},
        )


class SummarizeSystemIntelligenceAction(BaseAction):
    intent = Intent.SUMMARIZE_SYSTEM_INTELLIGENCE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SUMMARIZE_SYSTEM_INTELLIGENCE,
            summarize_system_intelligence(),
            data={"read_only": True},
        )


class SummarizeUnresolvedBlockersAction(BaseAction):
    intent = Intent.SUMMARIZE_UNRESOLVED_BLOCKERS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SUMMARIZE_UNRESOLVED_BLOCKERS,
            summarize_unresolved_blockers(),
            data={"read_only": True},
        )


class ExplainCurrentOperationalStateAction(BaseAction):
    intent = Intent.EXPLAIN_CURRENT_OPERATIONAL_STATE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.EXPLAIN_CURRENT_OPERATIONAL_STATE,
            explain_current_operational_state(),
            data={"read_only": True},
        )


class RecommendNextActionAction(BaseAction):
    intent = Intent.RECOMMEND_NEXT_ACTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.RECOMMEND_NEXT_ACTION,
            recommend_next_action(),
            data={"read_only": True},
        )


class WhatShouldWeInvestigateNextAction(BaseAction):
    intent = Intent.WHAT_SHOULD_WE_INVESTIGATE_NEXT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.WHAT_SHOULD_WE_INVESTIGATE_NEXT,
            what_should_we_investigate_next(),
            data={"read_only": True},
        )
