"""Phase 68 alpha actions."""

from __future__ import annotations

from actions.base import BaseAction
from alpha.report import show_alpha_report
from alpha.setup_check import format_alpha_setup_report, run_alpha_setup_checks
from core.results import result_success
from core.types import ActionStatus, CommandRequest, CommandResult, Intent


class AlphaSetupCheckAction(BaseAction):
    intent = Intent.ALPHA_SETUP_CHECK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        checks = run_alpha_setup_checks()
        body = format_alpha_setup_report(checks)
        all_pass = all(c.status.value == "PASS" for c in checks)
        return CommandResult(
            intent=Intent.ALPHA_SETUP_CHECK,
            status=ActionStatus.SUCCESS if all_pass else ActionStatus.FAILED,
            summary=body,
            data={"checks": [{"name": c.name, "status": c.status.value, "detail": c.detail} for c in checks]},
        )


class ShowAlphaReportAction(BaseAction):
    intent = Intent.SHOW_ALPHA_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(Intent.SHOW_ALPHA_REPORT, show_alpha_report(), data={"read_only": True})
