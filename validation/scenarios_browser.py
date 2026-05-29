"""50 strict browser task scenarios (Phase 66.1)."""

from __future__ import annotations

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import grade_browser_after_action

_CATEGORY = "Browser Task"


def _browser_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn
    from validation.strict_graders import _out, ScenarioStatus, ProviderKind

    scenarios: list[tuple[str, StrictScenarioFn]] = []

    def _mk_open(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import open_browser

            return grade_browser_after_action(open_browser("about:blank"), require_url=False)

        return _run

    for i in range(8):
        scenarios.append((f"browser_open_{i+1:02d}", _mk_open(i)))

    queries = [
        "nvidia earnings",
        "python asyncio",
        "jarvis assistant",
        "market news",
        "playwright docs",
        "openai api",
        "weather today",
        "cpu benchmarks",
    ]

    def _mk_search(query: str) -> StrictScenarioFn:
        def _run():
            from browser.runtime import search_web

            return grade_browser_after_action(search_web(query))

        return _run

    for i, q in enumerate(queries):
        scenarios.append((f"browser_search_{i+1:02d}", _mk_search(q)))

    def _mk_summarize(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import summarize_current_page

            return grade_browser_after_action(summarize_current_page())

        return _run

    for i in range(8):
        scenarios.append((f"browser_summarize_{i+1:02d}", _mk_summarize(i)))

    def _mk_health(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import get_browser_runtime_state
            from reliability.browser_health import show_browser_health

            body = show_browser_health()
            st = get_browser_runtime_state()
            if st.provider != "playwright":
                return _out(
                    ScenarioStatus.FAIL,
                    ProviderKind.UNAVAILABLE,
                    detail=body[:80],
                    error_message="browser_provider_unavailable",
                )
            return grade_browser_after_action(body, require_url=False)

        return _run

    for i in range(6):
        scenarios.append((f"browser_health_{i+1:02d}", _mk_health(i)))

    def _mk_nav(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import navigate_to_url

            return grade_browser_after_action(navigate_to_url("https://example.com"))

        return _run

    for i in range(8):
        scenarios.append((f"browser_nav_{i+1:02d}", _mk_nav(i)))

    def _mk_active(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import active_tab_status, get_browser_runtime_state

            body = active_tab_status()
            st = get_browser_runtime_state()
            if st.provider != "playwright":
                return _out(
                    ScenarioStatus.FAIL,
                    ProviderKind.UNAVAILABLE,
                    detail=body[:80],
                    error_message="browser_provider_unavailable",
                )
            return grade_browser_after_action(body)

        return _run

    for i in range(6):
        scenarios.append((f"browser_active_{i+1:02d}", _mk_active(i)))

    def _mk_find(idx: int) -> StrictScenarioFn:
        def _run():
            from browser.runtime import find_information_about

            return grade_browser_after_action(find_information_about(f"topic_{idx}"))

        return _run

    for i in range(6):
        scenarios.append((f"browser_find_{i+1:02d}", _mk_find(i)))

    return scenarios


def measure_browser_tasks() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _browser_scenarios())
