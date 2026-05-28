"""50 strict integration scenarios (Phase 67 — 40% real readonly target)."""

from __future__ import annotations

import config

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import grade_integration_mock, grade_integration_readonly

_CATEGORY = "Integrations (Email/Calendar)"


def _integration_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn
    from reliability.integrations_health import (
        show_urgent_emails,
        summarize_my_calendar,
        summarize_my_inbox,
    )
    from providers.daily_summary_provider import format_calendar_conflicts

    config.INTEGRATIONS_EMAIL_MODE = "gmail_readonly"
    config.INTEGRATIONS_CALENDAR_MODE = "gcal_readonly"

    scenarios: list[tuple[str, StrictScenarioFn]] = []

    for i in range(8):

        def _mk_inbox_real(limit: int = 20 + (i % 10)) -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_EMAIL_MODE = "gmail_readonly"
                body = summarize_my_inbox(limit)
                return grade_integration_readonly("REAL READONLY" in body, body)

            return _run

        scenarios.append((f"integration_inbox_real_{i+1:02d}", _mk_inbox_real()))

    for i in range(7):

        def _mk_urgent_real() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_EMAIL_MODE = "gmail_readonly"
                body = show_urgent_emails()
                return grade_integration_readonly("REAL READONLY" in body and "urgent" in body.lower(), body)

            return _run

        scenarios.append((f"integration_urgent_real_{i+1:02d}", _mk_urgent_real()))

    for i in range(3):

        def _mk_calendar_real() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_CALENDAR_MODE = "gcal_readonly"
                body = summarize_my_calendar()
                return grade_integration_readonly("REAL READONLY" in body, body)

            return _run

        scenarios.append((f"integration_calendar_real_{i+1:02d}", _mk_calendar_real()))

    for i in range(2):

        def _mk_conflicts_real() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_CALENDAR_MODE = "gcal_readonly"
                body = format_calendar_conflicts()
                return grade_integration_readonly("REAL READONLY" in body, body)

            return _run

        scenarios.append((f"integration_conflicts_real_{i+1:02d}", _mk_conflicts_real()))

    for i in range(10):

        def _mk_inbox_mock(limit: int = 15 + (i % 5)) -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_EMAIL_MODE = "mock"
                body = summarize_my_inbox(limit)
                return grade_integration_mock("MOCK MODE" in body, body)

            return _run

        scenarios.append((f"integration_inbox_mock_{i+1:02d}", _mk_inbox_mock()))

    for i in range(8):

        def _mk_urgent_mock() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_EMAIL_MODE = "mock"
                body = show_urgent_emails()
                return grade_integration_mock("MOCK MODE" in body, body)

            return _run

        scenarios.append((f"integration_urgent_mock_{i+1:02d}", _mk_urgent_mock()))

    for i in range(7):

        def _mk_calendar_mock() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_CALENDAR_MODE = "mock"
                body = summarize_my_calendar()
                return grade_integration_mock("MOCK MODE" in body, body)

            return _run

        scenarios.append((f"integration_calendar_mock_{i+1:02d}", _mk_calendar_mock()))

    for i in range(5):

        def _mk_conflicts_mock() -> StrictScenarioFn:
            def _run():
                config.INTEGRATIONS_CALENDAR_MODE = "mock"
                body = format_calendar_conflicts()
                return grade_integration_mock("MOCK MODE" in body, body)

            return _run

        scenarios.append((f"integration_conflicts_mock_{i+1:02d}", _mk_conflicts_mock()))

    return scenarios


def measure_integrations() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _integration_scenarios())
