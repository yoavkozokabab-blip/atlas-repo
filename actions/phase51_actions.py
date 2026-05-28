"""Phase 51 desktop awareness and operational reliability actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from computer_control.desktop_controller import (
    focus_terminal,
    show_focused_window,
    show_open_windows,
    switch_to_browser,
    switch_to_cursor,
    switch_to_dashboard,
)
from memory.task_memory import (
    clear_completed_task,
    continue_trading_investigation,
    pin_investigation,
    show_memory_state,
)
from operational.trading_operations_dashboard import show_trading_operations_dashboard
from vision.screen_system import show_screen_system_status


class _ReadOnlyPhase51Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowOpenWindowsAction(_ReadOnlyPhase51Action):
    intent = Intent.SHOW_OPEN_WINDOWS.value
    _fn = staticmethod(show_open_windows)


class ShowScreenSystemStatusAction(_ReadOnlyPhase51Action):
    intent = Intent.SHOW_SCREEN_SYSTEM_STATUS.value
    _fn = staticmethod(show_screen_system_status)


class ShowFocusedWindowAction(_ReadOnlyPhase51Action):
    intent = Intent.SHOW_FOCUSED_WINDOW.value
    _fn = staticmethod(show_focused_window)


class SwitchToBrowserAction(_ReadOnlyPhase51Action):
    intent = Intent.SWITCH_TO_BROWSER.value
    _fn = staticmethod(switch_to_browser)


class SwitchToCursorAction(_ReadOnlyPhase51Action):
    intent = Intent.SWITCH_TO_CURSOR.value
    _fn = staticmethod(switch_to_cursor)


class SwitchToDashboardAction(_ReadOnlyPhase51Action):
    intent = Intent.SWITCH_TO_DASHBOARD.value
    _fn = staticmethod(switch_to_dashboard)


class FocusTerminalAction(_ReadOnlyPhase51Action):
    intent = Intent.FOCUS_TERMINAL.value
    _fn = staticmethod(focus_terminal)


class ShowMemoryStateAction(_ReadOnlyPhase51Action):
    intent = Intent.SHOW_MEMORY_STATE.value
    _fn = staticmethod(show_memory_state)


class ClearCompletedTaskAction(_ReadOnlyPhase51Action):
    intent = Intent.CLEAR_COMPLETED_TASK.value
    _fn = staticmethod(clear_completed_task)


class PinInvestigationAction(BaseAction):
    intent = Intent.PIN_INVESTIGATION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        title = str(request.params.get("title") or "")
        if not title:
            raw = (request.raw_text or "").lower()
            if raw.startswith("pin investigation"):
                title = raw.replace("pin investigation", "", 1).strip()
        body = pin_investigation(title)
        return result_success(Intent.PIN_INVESTIGATION, body, data={"title": title})


class ContinueTradingInvestigationAction(_ReadOnlyPhase51Action):
    intent = Intent.CONTINUE_TRADING_INVESTIGATION.value
    _fn = staticmethod(continue_trading_investigation)


class ShowTradingOperationsDashboardAction(_ReadOnlyPhase51Action):
    intent = Intent.SHOW_TRADING_OPERATIONS_DASHBOARD.value
    _fn = staticmethod(show_trading_operations_dashboard)
