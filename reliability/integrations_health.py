"""Phase 65 Track F — integrations (read-only email/calendar).

Sprint 1 change (T-10 fix): acceptance cases now return SKIP (None, reason)
when no live credentials are configured, instead of PASS because the mock
marker is present.  A test that passes specifically because the system is
in mock mode is not evidence of production readiness.

Cases pass when:
  - Live credentials are configured AND the provider returns real data.
Cases are SKIPPED when:
  - No live credentials (mock mode).  Score is not affected.
Cases fail when:
  - Credentials are configured but the provider errors or returns mock data.
"""

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


def _email_mode() -> str:
    from providers.daily_summary_provider import get_email_provider_mode

    return get_email_provider_mode()


def _calendar_mode() -> str:
    from providers.daily_summary_provider import get_calendar_provider_mode

    return get_calendar_provider_mode()


def run_integrations_acceptance() -> TrackScore:
    score = TrackScore(track="Integrations", current_pct=0.0, target_pct=60.0)

    def _inbox() -> tuple[bool | None, str]:
        # T-10 fix: SKIP when mock; test real data when credentials exist.
        mode = _email_mode()
        if mode != "gmail_readonly":
            return None, f"SKIP: email_mode='{mode}' (no live credentials)"
        body = summarize_my_inbox(20)
        ok = bool(body) and _MOCK_MARKER not in body
        return ok, body[:80]

    def _urgent() -> tuple[bool | None, str]:
        mode = _email_mode()
        if mode != "gmail_readonly":
            return None, f"SKIP: email_mode='{mode}'"
        body = show_urgent_emails()
        ok = bool(body) and _MOCK_MARKER not in body
        return ok, body[:80]

    def _calendar() -> tuple[bool | None, str]:
        mode = _calendar_mode()
        if mode != "gcal_readonly":
            return None, f"SKIP: calendar_mode='{mode}' (no live credentials)"
        body = summarize_my_calendar()
        ok = bool(body) and _MOCK_MARKER not in body and "schedule" in body.lower()
        return ok, body[:80]

    def _conflicts() -> tuple[bool | None, str]:
        mode = _calendar_mode()
        if mode != "gcal_readonly":
            return None, f"SKIP: calendar_mode='{mode}'"
        from providers.daily_summary_provider import get_calendar_provider

        body = get_calendar_provider().find_conflicts().format("Conflicts")
        ok = bool(body) and _MOCK_MARKER not in body
        return ok, body[:80]

    def _no_mutations() -> tuple[bool, str]:
        # Real interface check — always runs regardless of mode.
        from providers import daily_summary_provider as dsp

        forbidden = ("send", "delete", "update", "create_event")
        for name in forbidden:
            if hasattr(dsp.EmailProvider, name) or hasattr(dsp.CalendarProvider, name):
                return False, f"forbidden method present: {name}"
        return True, "read-only interface confirmed"

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
    # Report blockers based on actual skip state.
    skipped_data = sum(1 for c in score.cases if c.skipped)
    if skipped_data > 0:
        score.blockers.append(
            f"Live email/calendar adapters not connected "
            f"({skipped_data} data cases SKIPPED — no OAuth credentials)."
        )
        score.recommendations.append(
            "Set INTEGRATIONS_EMAIL_MODE=gmail_readonly and INTEGRATIONS_CALENDAR_MODE=gcal_readonly "
            "with valid OAuth tokens to enable live acceptance testing."
        )
    write_report(reports_dir() / "integrations_report.md", format_track_report(score).splitlines())
    return score
