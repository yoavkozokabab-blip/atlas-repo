"""Phase 73A browser trust repair tests."""

from __future__ import annotations

import pytest

from actions.phase60_actions import (
    CompareThesePagesAction,
    CompareTheseResultsAction,
    OpenBrowserAction,
    SearchWebForAction,
    SummarizeThisPageAction,
    WhatTabIsActiveAction,
)
from actions.phase62_browser_actions import (
    ExtractKeyFactsFromThisPageAction,
    FindInformationAboutAction,
    SaveBrowserResearchReportAction,
)
from brain.router import CommandRouter
from core import confirmation
from core.types import ActionStatus, CommandRequest, Intent
from tooluse import pending
from tooluse.contracts import Observation, PlanStep, StepOutcome
from tooluse.recovery import RecoveryDecision
import actions.tool_use_actions as tool_actions


def _reset_legacy_browser(provider: str) -> None:
    import browser.runtime as runtime

    runtime._playwright = None
    runtime._browser = None
    runtime._context = None
    runtime._active_page = None
    runtime._last_search_results = []
    runtime._state.provider = provider
    runtime._state.session_active = False
    runtime._state.browser_visible = False
    runtime._state.browser_process_alive = False
    runtime._state.current_url = ""
    runtime._state.active_tab_title = ""
    runtime._state.last_dom_excerpt = ""
    runtime._state.last_screenshot_path = ""
    runtime._state.last_action_success = False
    runtime._state.last_exception = "test provider unavailable"


@pytest.fixture(autouse=True)
def _isolate_browser(monkeypatch, tmp_path):
    import browser.runtime as runtime
    from tooluse import audit

    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    audit.reset_for_tests()
    confirmation.clear_all()
    pending.reset_for_tests()
    tool_actions.set_tool_provider_factory(None)
    _reset_legacy_browser("unavailable")

    def fail_session() -> bool:
        runtime._state.provider = runtime._state.provider or "unavailable"
        runtime._state.session_active = False
        runtime._state.browser_visible = False
        runtime._state.browser_process_alive = False
        runtime._state.last_action_success = False
        runtime._state.last_exception = "playwright unavailable for test"
        return False

    monkeypatch.setattr(runtime, "_ensure_playwright_session", fail_session)
    yield
    confirmation.clear_all()
    pending.reset_for_tests()
    tool_actions.set_tool_provider_factory(None)
    _reset_legacy_browser("unavailable")


@pytest.mark.parametrize("provider", ["mock", "unavailable", "degraded", "simulated"])
@pytest.mark.parametrize(
    "action,command_request",
    [
        (
            OpenBrowserAction(),
            CommandRequest(raw_text="open browser", intent=Intent.OPEN_BROWSER),
        ),
        (
            SearchWebForAction(),
            CommandRequest(
                raw_text="search web for python release notes",
                intent=Intent.SEARCH_WEB_FOR,
                params={"query": "python release notes"},
            ),
        ),
        (
            SummarizeThisPageAction(),
            CommandRequest(raw_text="summarize this page", intent=Intent.SUMMARIZE_THIS_PAGE),
        ),
        (
            CompareTheseResultsAction(),
            CommandRequest(raw_text="compare these results", intent=Intent.COMPARE_THESE_RESULTS),
        ),
        (
            CompareThesePagesAction(),
            CommandRequest(raw_text="compare these pages", intent=Intent.COMPARE_THESE_PAGES),
        ),
        (
            WhatTabIsActiveAction(),
            CommandRequest(raw_text="what tab is active", intent=Intent.WHAT_TAB_IS_ACTIVE),
        ),
        (
            FindInformationAboutAction(),
            CommandRequest(
                raw_text="find information about python release notes",
                intent=Intent.FIND_INFORMATION_ABOUT,
                params={"query": "python release notes"},
            ),
        ),
        (
            ExtractKeyFactsFromThisPageAction(),
            CommandRequest(
                raw_text="extract key facts from this page",
                intent=Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE,
            ),
        ),
        (
            SaveBrowserResearchReportAction(),
            CommandRequest(
                raw_text="save browser research report",
                intent=Intent.SAVE_BROWSER_RESEARCH_REPORT,
            ),
        ),
    ],
)
def test_legacy_browser_actions_never_succeed_without_trusted_provider(provider, action, command_request):
    _reset_legacy_browser(provider)

    result = action.execute(command_request)

    assert result.status in {ActionStatus.BLOCKED, ActionStatus.FAILED}
    assert result.status != ActionStatus.SUCCESS


def test_legacy_router_command_fails_honestly_when_browser_unavailable():
    _reset_legacy_browser("unavailable")

    result = CommandRouter().route("search web for python release notes")

    assert result.status == ActionStatus.BLOCKED
    assert "unavailable" in (result.error or result.summary).lower()


class MockLabeledToolProvider:
    """Claims to be real, but reports a mock provider label in observations."""

    def __init__(self) -> None:
        self.closed = False

    def is_real(self) -> bool:
        return True

    def observe(self) -> Observation:
        return Observation(
            real=True,
            provider="mock",
            url="https://example.com/mock",
            title="Mock Page",
            links=[{"title": "Example", "href": "https://example.com/real"}],
            visible_text="This text is long enough that summary verification would pass without the trust guard.",
        )

    def execute(self, step: PlanStep) -> StepOutcome:
        return StepOutcome(ok=True, detail=f"mock did {step.kind.value}")

    def apply_recovery(self, decision: RecoveryDecision, step: PlanStep) -> None:
        del decision, step

    def close(self) -> None:
        self.closed = True


def test_tooluse_mock_labeled_provider_cannot_produce_success():
    provider = MockLabeledToolProvider()
    tool_actions.set_tool_provider_factory(lambda: provider)
    router = CommandRouter()

    preview = router.route("run tool task python release notes")
    assert preview.status == ActionStatus.CONFIRMATION_REQUIRED

    result = router.route("yes")

    assert result.status != ActionStatus.SUCCESS
    assert result.status == ActionStatus.FAILED
    assert "mock" in result.summary.lower() or "trusted real provider" in result.summary.lower()
    assert provider.closed is True


def test_tooluse_unavailable_provider_blocks_before_success():
    class UnavailableProvider(MockLabeledToolProvider):
        def is_real(self) -> bool:
            return False

        def observe(self) -> Observation:
            return Observation(real=False, provider="unavailable")

    tool_actions.set_tool_provider_factory(UnavailableProvider)
    router = CommandRouter()

    preview = router.route("run tool task python release notes")
    assert preview.status == ActionStatus.CONFIRMATION_REQUIRED

    result = router.route("yes")

    assert result.status == ActionStatus.BLOCKED
    assert result.status != ActionStatus.SUCCESS
