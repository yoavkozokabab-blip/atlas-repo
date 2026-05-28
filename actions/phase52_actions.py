"""Phase 52 background task and notification actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from assistant.notifications import clear_notifications, show_notifications
from runtime.background_tasks import get_engine


class ShowRunningTasksAction(BaseAction):
    intent = Intent.SHOW_RUNNING_TASKS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = get_engine().format_task_list(get_engine().list_running(), title="Running tasks")
        return result_success(Intent.SHOW_RUNNING_TASKS, body, data={"read_only": True})


class ShowCompletedTasksAction(BaseAction):
    intent = Intent.SHOW_COMPLETED_TASKS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = get_engine().format_task_list(get_engine().list_completed(), title="Completed tasks")
        return result_success(Intent.SHOW_COMPLETED_TASKS, body, data={"read_only": True})


class ShowFailedTasksAction(BaseAction):
    intent = Intent.SHOW_FAILED_TASKS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = get_engine().format_task_list(get_engine().list_failed(), title="Failed tasks")
        return result_success(Intent.SHOW_FAILED_TASKS, body, data={"read_only": True})


class ShowRecentResultsAction(BaseAction):
    intent = Intent.SHOW_RECENT_RESULTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = get_engine().format_task_list(
            get_engine().list_recent_results(),
            title="Recent task results",
        )
        return result_success(Intent.SHOW_RECENT_RESULTS, body, data={"read_only": True})


class CancelTaskAction(BaseAction):
    intent = Intent.CANCEL_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw_id = request.params.get("task_id")
        if raw_id is None:
            return result_failed(Intent.CANCEL_TASK, "Specify task id: cancel task 3")
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            return result_failed(Intent.CANCEL_TASK, f"Invalid task id: {raw_id!r}")
        ok, message = get_engine().cancel_task(task_id)
        if not ok:
            return result_failed(Intent.CANCEL_TASK, message)
        return result_success(Intent.CANCEL_TASK, message, data={"task_id": task_id})


class RerunLastBackgroundTaskAction(BaseAction):
    intent = Intent.RERUN_LAST_BACKGROUND_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        task_id, message = get_engine().rerun_last()
        if task_id is None:
            return result_failed(Intent.RERUN_LAST_BACKGROUND_TASK, message)
        return result_success(
            Intent.RERUN_LAST_BACKGROUND_TASK,
            message,
            data={"task_id": task_id},
        )


class ShowNotificationsAction(BaseAction):
    intent = Intent.SHOW_NOTIFICATIONS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        unread = bool(request.params.get("unread_only"))
        body = show_notifications(unread_only=unread)
        return result_success(Intent.SHOW_NOTIFICATIONS, body, data={"read_only": True})


class ClearNotificationsAction(BaseAction):
    intent = Intent.CLEAR_NOTIFICATIONS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = clear_notifications()
        return result_success(Intent.CLEAR_NOTIFICATIONS, body)


class ExplainLastResultAction(BaseAction):
    intent = Intent.EXPLAIN_LAST_RESULT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = get_engine().explain_last_result()
        return result_success(Intent.EXPLAIN_LAST_RESULT, body, data={"read_only": True})
