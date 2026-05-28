"""Email/calendar provider abstraction — mock or read-only real (Phase 67)."""

from __future__ import annotations

from dataclasses import dataclass

import config

_MOCK_BANNER = "MOCK MODE | NO REAL EXTERNAL ACCESS | SIMULATED OUTPUT ONLY"


@dataclass(frozen=True)
class DailySummary:
    urgent: list[str]
    waiting_on_me: list[str]
    schedule: list[str]
    risks: list[str]
    recommended_actions: list[str]

    def format(self, title: str, *, banner: str | None = None) -> str:
        lines = [title, banner or _MOCK_BANNER]
        lines.extend(_section("urgent", self.urgent))
        lines.extend(_section("waiting_on_me", self.waiting_on_me))
        lines.extend(_section("schedule", self.schedule))
        lines.extend(_section("risks", self.risks))
        lines.extend(_section("recommended_actions", self.recommended_actions))
        return "\n".join(lines)


class EmailProvider:
    def summarize_last(self, count: int) -> DailySummary:
        return DailySummary(
            urgent=[
                "Security review thread unresolved (deadline today 17:00).",
                "Client reply requested on pricing amendment.",
            ],
            waiting_on_me=[
                "Approve draft release notes before QA sync.",
                "Reply to hiring loop schedule request.",
            ],
            schedule=[f"Processed mock inbox sample: {max(1, int(count))} emails."],
            risks=["Two unanswered client threads older than 48h."],
            recommended_actions=[
                "Send pricing amendment response first.",
                "Delegate release-note wording review.",
            ],
        )


class CalendarProvider:
    def summarize_day(self) -> DailySummary:
        return DailySummary(
            urgent=["Back-to-back meetings from 14:00 to 16:30 block deep work."],
            waiting_on_me=["Confirm architecture review attendees."],
            schedule=[
                "11:00 product sync (30m)",
                "13:00 one-on-one (45m)",
                "15:00 partner call (60m)",
            ],
            risks=["No explicit buffer before partner call."],
            recommended_actions=[
                "Create a 25-minute prep block before 15:00 call.",
                "Move one low-priority meeting to tomorrow.",
            ],
        )

    def find_conflicts(self) -> DailySummary:
        return DailySummary(
            urgent=["Two overlapping holds at 15:00 and 15:30."],
            waiting_on_me=["Need decision: keep partner call or internal debrief."],
            schedule=["Conflict window: 15:00-16:00."],
            risks=["Loss of prep time for partner call."],
            recommended_actions=["Decline the internal debrief and keep partner call."],
        )


def get_email_provider_mode() -> str:
    return getattr(config, "INTEGRATIONS_EMAIL_MODE", "mock") or "mock"


def get_calendar_provider_mode() -> str:
    return getattr(config, "INTEGRATIONS_CALENDAR_MODE", "mock") or "mock"


def get_email_provider() -> EmailProvider:
    mode = get_email_provider_mode()
    if mode == "gmail_readonly":
        from providers.readonly_integrations import ReadonlyEmailProvider

        return ReadonlyEmailProvider()
    return EmailProvider()


def get_calendar_provider() -> CalendarProvider:
    mode = get_calendar_provider_mode()
    if mode == "gcal_readonly":
        from providers.readonly_integrations import ReadonlyCalendarProvider

        return ReadonlyCalendarProvider()
    return CalendarProvider()


def format_email_summary(count: int) -> str:
    provider = get_email_provider()
    summary = provider.summarize_last(count)
    banner = _MOCK_BANNER
    if hasattr(provider, "format_banner"):
        banner = provider.format_banner()
    return summary.format("Inbox summary", banner=banner)


def format_calendar_summary() -> str:
    provider = get_calendar_provider()
    summary = provider.summarize_day()
    banner = _MOCK_BANNER
    if hasattr(provider, "format_banner"):
        banner = provider.format_banner()
    return summary.format("Calendar summary", banner=banner)


def format_calendar_conflicts() -> str:
    provider = get_calendar_provider()
    summary = provider.find_conflicts()
    banner = _MOCK_BANNER
    if hasattr(provider, "format_banner"):
        banner = provider.format_banner()
    return summary.format("Conflicts", banner=banner)


def _section(name: str, items: list[str]) -> list[str]:
    lines = [f"{name}:"]
    if not items:
        lines.append("  - none")
        return lines
    lines.extend([f"  - {item}" for item in items])
    return lines
