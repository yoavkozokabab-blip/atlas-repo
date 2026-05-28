"""Phase 65 product hardening actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent


class ShowVoiceHealthAction(BaseAction):
    intent = Intent.SHOW_VOICE_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.voice_health import show_voice_health

        return result_success(Intent.SHOW_VOICE_HEALTH, show_voice_health(), data={"read_only": True})


class RepairMemoryStoreAction(BaseAction):
    intent = Intent.REPAIR_MEMORY_STORE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from memory.repair import repair_memory_store

        return result_success(Intent.REPAIR_MEMORY_STORE, repair_memory_store())


class ShowBrowserHealthAction(BaseAction):
    intent = Intent.SHOW_BROWSER_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.browser_health import show_browser_health

        return result_success(Intent.SHOW_BROWSER_HEALTH, show_browser_health(), data={"read_only": True})


class ShowDesktopOperatorHealthAction(BaseAction):
    intent = Intent.SHOW_DESKTOP_OPERATOR_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.desktop_health import show_desktop_operator_health

        return result_success(
            Intent.SHOW_DESKTOP_OPERATOR_HEALTH,
            show_desktop_operator_health(),
            data={"read_only": True},
        )


class ShowSystemHealthAction(BaseAction):
    intent = Intent.SHOW_SYSTEM_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.system_health import show_system_health

        return result_success(Intent.SHOW_SYSTEM_HEALTH, show_system_health(), data={"read_only": True})


class ShowPerformanceReportAction(BaseAction):
    intent = Intent.SHOW_PERFORMANCE_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.performance_health import show_performance_report

        return result_success(Intent.SHOW_PERFORMANCE_REPORT, show_performance_report(), data={"read_only": True})


class SummarizeMyInboxAction(BaseAction):
    intent = Intent.SUMMARIZE_MY_INBOX.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.integrations_health import summarize_my_inbox

        return result_success(Intent.SUMMARIZE_MY_INBOX, summarize_my_inbox(), data={"read_only": True})


class ShowUrgentEmailsAction(BaseAction):
    intent = Intent.SHOW_URGENT_EMAILS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.integrations_health import show_urgent_emails

        return result_success(Intent.SHOW_URGENT_EMAILS, show_urgent_emails(), data={"read_only": True})


class SummarizeMyCalendarAction(BaseAction):
    intent = Intent.SUMMARIZE_MY_CALENDAR.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.integrations_health import summarize_my_calendar

        return result_success(Intent.SUMMARIZE_MY_CALENDAR, summarize_my_calendar(), data={"read_only": True})


class GenerateProductReadinessReportAction(BaseAction):
    intent = Intent.GENERATE_PRODUCT_READINESS_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from reliability.product_readiness import generate_product_readiness_report

        body = generate_product_readiness_report()
        return result_success(
            Intent.GENERATE_PRODUCT_READINESS_REPORT,
            "Product readiness report generated.\n" + body[:1200],
            data={"read_only": True},
        )
