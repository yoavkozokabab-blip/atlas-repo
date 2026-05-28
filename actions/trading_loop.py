"""Trading loop control (allowlisted scripts only)."""

from __future__ import annotations

from actions.base import BaseAction
from actions.powershell import run_allowlisted_script
from config import TRADING_DAILY_LOOP_SCRIPT, TRADING_WEEKLY_LOOP_SCRIPT
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


class RunLiveDailyLoopAction(BaseAction):
    intent = Intent.RUN_LIVE_DAILY_LOOP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            msg = run_allowlisted_script(TRADING_DAILY_LOOP_SCRIPT)
            return result_success(Intent.RUN_LIVE_DAILY_LOOP, msg)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return result_failed(
                Intent.RUN_LIVE_DAILY_LOOP,
                str(exc),
                error=str(exc),
            )


class RunLiveWeeklyLoopAction(BaseAction):
    intent = Intent.RUN_LIVE_WEEKLY_LOOP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            msg = run_allowlisted_script(TRADING_WEEKLY_LOOP_SCRIPT)
            return result_success(Intent.RUN_LIVE_WEEKLY_LOOP, msg)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            return result_failed(
                Intent.RUN_LIVE_WEEKLY_LOOP,
                str(exc),
                error=str(exc),
            )
