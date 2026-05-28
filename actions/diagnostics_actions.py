"""Read-only diagnostics actions (cross-source analysis)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from diagnostics import (
    analyze_current_screen,
    diagnose_dashboard,
    diagnose_recent_errors,
    diagnose_trading_loop,
    explain_last_failure,
    run_diagnostics,
    suggest_next_steps,
)
from diagnostics.command_audit import (
    DEFAULT_AUDIT_LIMIT,
    format_audit_report,
    read_last_audit_entries,
)


def _report_result(intent: Intent, report) -> CommandResult:
    return result_success(
        intent,
        report.summary,
        data=report.to_dict(),
        next_suggestions=report.findings[0].suggested_steps[:4]
        if report.findings
        else [],
    )


def _run(intent: Intent, fn) -> CommandResult:
    try:
        report = fn()
        return _report_result(intent, report)
    except Exception as exc:
        return result_failed(
            intent,
            f"Diagnostics failed: {exc}",
            error=str(exc),
        )


class RunDiagnosticsAction(BaseAction):
    intent = Intent.RUN_DIAGNOSTICS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.RUN_DIAGNOSTICS, run_diagnostics)


class DiagnoseDashboardAction(BaseAction):
    intent = Intent.DIAGNOSE_DASHBOARD.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.DIAGNOSE_DASHBOARD, diagnose_dashboard)


class DiagnoseTradingLoopAction(BaseAction):
    intent = Intent.DIAGNOSE_TRADING_LOOP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.DIAGNOSE_TRADING_LOOP, diagnose_trading_loop)


class DiagnoseRecentErrorsAction(BaseAction):
    intent = Intent.DIAGNOSE_RECENT_ERRORS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.DIAGNOSE_RECENT_ERRORS, diagnose_recent_errors)


class AnalyzeCurrentScreenAction(BaseAction):
    intent = Intent.ANALYZE_CURRENT_SCREEN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.ANALYZE_CURRENT_SCREEN, analyze_current_screen)


class ExplainLastFailureAction(BaseAction):
    intent = Intent.EXPLAIN_LAST_FAILURE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.EXPLAIN_LAST_FAILURE, explain_last_failure)


class SuggestNextStepsAction(BaseAction):
    intent = Intent.SUGGEST_NEXT_STEPS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run(Intent.SUGGEST_NEXT_STEPS, suggest_next_steps)


class ShowCommandAuditAction(BaseAction):
    intent = Intent.SHOW_COMMAND_AUDIT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        limit = DEFAULT_AUDIT_LIMIT
        raw_limit = request.params.get("limit")
        if raw_limit is not None:
            try:
                limit = max(1, min(100, int(raw_limit)))
            except (TypeError, ValueError):
                pass
        entries = read_last_audit_entries(limit)
        body = format_audit_report(entries, limit=limit)
        return result_success(
            Intent.SHOW_COMMAND_AUDIT,
            body,
            data={"count": len(entries), "limit": limit, "read_only": True},
        )
