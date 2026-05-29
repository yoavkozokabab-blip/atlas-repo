"""Phase 62 browser agent loop actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_blocked, result_clarification, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _browser_failure(intent: Intent, body: str, provider: str) -> CommandResult:
    if provider != "playwright":
        return result_blocked(intent, body, error="real browser provider unavailable")
    return result_failed(intent, body)


class FindInformationAboutAction(BaseAction):
    intent = Intent.FIND_INFORMATION_ABOUT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or "").strip()
        if not query:
            raw = request.raw_text.lower()
            marker = "find information about"
            if marker in raw:
                query = request.raw_text[raw.find(marker) + len(marker) :].strip()
        if not query:
            return result_clarification(Intent.FIND_INFORMATION_ABOUT, "What information should I find?")
        from browser.runtime import browser_task_plan, find_information_about, get_browser_runtime_state

        plan = browser_task_plan(query)
        body = f"{plan}\n\n{find_information_about(query)}"
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.FIND_INFORMATION_ABOUT, body, state.provider)
        return result_success(Intent.FIND_INFORMATION_ABOUT, body, data={"query": query})


class OpenBestResultAction(BaseAction):
    intent = Intent.OPEN_BEST_RESULT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import get_browser_runtime_state, open_best_result

        body = open_best_result()
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.OPEN_BEST_RESULT, body, state.provider)
        return result_success(Intent.OPEN_BEST_RESULT, body)


class SummarizeTopResultsAction(BaseAction):
    intent = Intent.SUMMARIZE_TOP_RESULTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import get_browser_runtime_state, summarize_top_results

        body = summarize_top_results()
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.SUMMARIZE_TOP_RESULTS, body, state.provider)
        return result_success(Intent.SUMMARIZE_TOP_RESULTS, body, data={"read_only": True})


class CompareTheseSearchResultsAction(BaseAction):
    intent = Intent.COMPARE_THESE_SEARCH_RESULTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import compare_search_results, get_browser_runtime_state

        body = compare_search_results()
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.COMPARE_THESE_SEARCH_RESULTS, body, state.provider)
        return result_success(Intent.COMPARE_THESE_SEARCH_RESULTS, body, data={"read_only": True})


class ExtractKeyFactsFromThisPageAction(BaseAction):
    intent = Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import extract_key_facts_from_page, get_browser_runtime_state

        body = extract_key_facts_from_page()
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE, body, state.provider)
        return result_success(Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE, body)


class SaveBrowserResearchReportAction(BaseAction):
    intent = Intent.SAVE_BROWSER_RESEARCH_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import get_browser_runtime_state, save_browser_research_report

        body = save_browser_research_report()
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return _browser_failure(Intent.SAVE_BROWSER_RESEARCH_REPORT, body, state.provider)
        return result_success(Intent.SAVE_BROWSER_RESEARCH_REPORT, body)

