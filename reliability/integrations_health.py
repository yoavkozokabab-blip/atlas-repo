"""Phase 65 Track F — integrations (read-only email/calendar)."""

from __future__ import annotations

from reliability.hardening_core import TrackScore, format_track_report, reports_dir, run_case, write_report

_MOCK_MARKER = "MOCK MODE"


def summarize_my_inbox(count: int = 50) -> str:
    from providers.daily_summary_provider import format_email_summary

    return format_email_summary(count)


def show_urgent_emails() -> str:
    from providers.daily_summary_provider import get_email_provider, get_email_provider_mode

    provider = get_email_provider()
    summary = provider.summarize_last(30)
    mode = get_email_provider_mode()
    if mode == "gmail_readonly" and hasattr(provider, "format_banner"):
        lines = ["Urgent emails (read-only):", provider.format_banner()]
    else:
        lines = ["Urgent emails (read-only):", _MOCK_MARKER]
    if not summary.urgent:
        lines.append("  - none")
    else:
        lines.extend([f"  - {x}" for x in summary.urgent])
    return "\n".join(lines)


def summarize_my_calendar() -> str:
    from providers.daily_summary_provider import format_calendar_summary

    return format_calendar_summary()


def run_integrations_acceptance() -> TrackScore:
    score = TrackScore(track="Integrations", current_pct=0.0, target_pct=60.0)

    def _inbox() -> tuple[bool, str]:
        body = summarize_my_inbox(20)
        return _MOCK_MARKER in body and "urgent" in body.lower(), "mock read-only"

    def _urgent() -> tuple[bool, str]:
        body = show_urgent_emails()
        return _MOCK_MARKER in body, body[:80]

    def _calendar() -> tuple[bool, str]:
        body = summarize_my_calendar()
        return _MOCK_MARKER in body and "schedule" in body.lower(), "mock read-only"

    def _conflicts() -> tuple[bool, str]:
        from providers.daily_summary_provider import get_calendar_provider

        body = get_calendar_provider().find_conflicts().format("Conflicts")
        return _MOCK_MARKER in body, "conflicts mock"

    def _no_mutations() -> tuple[bool, str]:
        from providers import daily_summary_provider as dsp

        forbidden = ("send", "delete", "update", "create_event")
        for name in forbidden:
            if hasattr(dsp.EmailProvider, name) or hasattr(dsp.CalendarProvider, name):
                return False, f"forbidden method present: {name}"
        return True, "read-only interface"

    score.cases.extend(
        [
            run_case("summarize_inbox", _inbox),
            run_case("urgent_emails", _urgent),
            run_case("summarize_calendar", _calendar),
            run_case("find_conflicts", _conflicts),
            run_case("read_only_guard", _no_mutations),
        ]
    )
    score.finalize_score()
    score.blockers.append("Live email/calendar adapters not connected (mock-only).")
    score.recommendations.append("Wire OAuth read-only providers behind existing summarize commands.")
    write_report(reports_dir() / "integrations_report.md", format_track_report(score).splitlines())
    return score
