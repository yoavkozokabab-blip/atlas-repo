"""Phase 50 computer control, context memory, and trading operations actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from assistant.operational_suggestions import show_operational_suggestions
from computer_control.desktop_controller import search_local_reports
from memory.task_memory import (
    continue_investigation,
    open_last_report,
    resume_last_task,
    show_recent_investigations,
    what_was_i_doing,
)
from operational.trading_operations import (
    compare_today_vs_yesterday,
    explain_why_no_trades_today,
    show_current_execution_risk,
    show_top_operational_blockers,
    summarize_live_engine_status,
    summarize_trading_health,
)
from operational.unified_state import (
    phase50_status,
    show_active_systems,
    show_current_state,
    show_runtime_summary,
)
from vision.context_engine import (
    explain_visible_error,
    inspect_current_chart,
    summarize_current_report,
    summarize_current_screen,
    what_am_i_looking_at,
)


class _ReadOnlyPhase50Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class _ParamPhase50Action(BaseAction):
    intent: str
    _fn = None
    _param_key: str = "query"

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = request.raw_text or ""
        value = str(request.params.get(self._param_key) or "")
        if not value:
            parts = raw.split(" for ", 1)
            if len(parts) == 2:
                value = parts[1].strip()
            elif raw.lower().startswith("search reports"):
                value = raw[14:].strip()
        body = self._fn(value)
        return result_success(Intent(self.intent), body, data={self._param_key: value})


class WhatAmILookingAtAction(_ReadOnlyPhase50Action):
    intent = Intent.WHAT_AM_I_LOOKING_AT.value
    _fn = staticmethod(what_am_i_looking_at)


class SummarizeCurrentScreenAction(_ReadOnlyPhase50Action):
    intent = Intent.SUMMARIZE_CURRENT_SCREEN.value
    _fn = staticmethod(summarize_current_screen)


class SummarizeTradingHealthAction(_ReadOnlyPhase50Action):
    intent = Intent.SUMMARIZE_TRADING_HEALTH.value
    _fn = staticmethod(summarize_trading_health)


class ExplainWhyNoTradesTodayAction(_ReadOnlyPhase50Action):
    intent = Intent.EXPLAIN_WHY_NO_TRADES_TODAY.value
    _fn = staticmethod(explain_why_no_trades_today)


class CompareTodayVsYesterdayAction(_ReadOnlyPhase50Action):
    intent = Intent.COMPARE_TODAY_VS_YESTERDAY.value
    _fn = staticmethod(compare_today_vs_yesterday)


class ShowTopOperationalBlockersAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_TOP_OPERATIONAL_BLOCKERS.value
    _fn = staticmethod(show_top_operational_blockers)


class ShowCurrentExecutionRiskAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_CURRENT_EXECUTION_RISK.value
    _fn = staticmethod(show_current_execution_risk)


class SummarizeLiveEngineStatusAction(_ReadOnlyPhase50Action):
    intent = Intent.SUMMARIZE_LIVE_ENGINE_STATUS.value
    _fn = staticmethod(summarize_live_engine_status)


class ResumeLastTaskAction(_ReadOnlyPhase50Action):
    intent = Intent.RESUME_LAST_TASK.value
    _fn = staticmethod(resume_last_task)


class ShowRecentInvestigationsAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_RECENT_INVESTIGATIONS.value
    _fn = staticmethod(show_recent_investigations)


class ContinueInvestigationAction(_ReadOnlyPhase50Action):
    intent = Intent.CONTINUE_INVESTIGATION.value
    _fn = staticmethod(continue_investigation)


class OpenLastReportAction(_ReadOnlyPhase50Action):
    intent = Intent.OPEN_LAST_REPORT.value
    _fn = staticmethod(open_last_report)


class SearchReportsAction(_ParamPhase50Action):
    intent = Intent.SEARCH_REPORTS.value
    _param_key = "query"
    _fn = staticmethod(search_local_reports)


class ShowCurrentStateAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_CURRENT_STATE.value
    _fn = staticmethod(show_current_state)


class ShowActiveSystemsAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_ACTIVE_SYSTEMS.value
    _fn = staticmethod(show_active_systems)


class ShowRuntimeSummaryAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_RUNTIME_SUMMARY.value
    _fn = staticmethod(show_runtime_summary)


class ShowOperationalSuggestionsAction(_ReadOnlyPhase50Action):
    intent = Intent.SHOW_OPERATIONAL_SUGGESTIONS.value
    _fn = staticmethod(show_operational_suggestions)


class Phase50StatusAction(_ReadOnlyPhase50Action):
    intent = Intent.PHASE50_STATUS.value
    _fn = staticmethod(phase50_status)


class WhatWasIDoingMemoryAction(_ReadOnlyPhase50Action):
    """Alias path for 'what was I doing' using task memory."""

    intent = Intent.RESUME_LAST_TASK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = what_was_i_doing()
        return result_success(Intent.RESUME_LAST_TASK, body, data={"read_only": True})
