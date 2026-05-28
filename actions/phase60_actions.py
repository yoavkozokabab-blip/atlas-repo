"""Phase 60 core utility actions (browser + email/calendar summaries)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_clarification, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


class ShowMemoryDebugAction(BaseAction):
    intent = Intent.SHOW_MEMORY_DEBUG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from actions.memory_actions import ListMemoryAction

        req = request.model_copy(update={"raw_text": "show memory debug"})
        return ListMemoryAction().execute(req)


class ShowBrowserDebugAction(BaseAction):
    intent = Intent.SHOW_BROWSER_DEBUG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import get_browser_runtime_state

        return result_success(Intent.SHOW_BROWSER_DEBUG, get_browser_runtime_state().format_debug())


class OpenBrowserAction(BaseAction):
    intent = Intent.OPEN_BROWSER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        url = str(request.params.get("url") or "").strip() or "about:blank"
        from browser.runtime import get_browser_runtime_state, open_browser

        body = open_browser(url)
        state = get_browser_runtime_state()
        if not state.last_action_success:
            return result_failed(Intent.OPEN_BROWSER, body)
        return result_success(Intent.OPEN_BROWSER, body, data={"url": url})


class SearchWebForAction(BaseAction):
    intent = Intent.SEARCH_WEB_FOR.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or "").strip()
        if not query:
            raw = request.raw_text.lower()
            marker = "search web for"
            if marker in raw:
                query = request.raw_text[raw.find(marker) + len(marker) :].strip()
        if not query:
            return result_clarification(Intent.SEARCH_WEB_FOR, "What should I search for?")
        from browser.runtime import get_browser_runtime_state, search_web

        body = search_web(query)
        state = get_browser_runtime_state()
        if not state.last_action_success and state.provider != "mock":
            return result_failed(Intent.SEARCH_WEB_FOR, body)
        return result_success(Intent.SEARCH_WEB_FOR, body, data={"query": query, "read_only": True})


class SummarizeThisPageAction(BaseAction):
    intent = Intent.SUMMARIZE_THIS_PAGE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import get_browser_runtime_state, summarize_current_page

        body = summarize_current_page()
        state = get_browser_runtime_state()
        if not state.last_action_success and state.provider != "mock":
            return result_failed(Intent.SUMMARIZE_THIS_PAGE, body)
        return result_success(Intent.SUMMARIZE_THIS_PAGE, body, data={"read_only": True})


class CompareTheseResultsAction(BaseAction):
    intent = Intent.COMPARE_THESE_RESULTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import compare_latest_results, get_browser_runtime_state

        body = compare_latest_results()
        state = get_browser_runtime_state()
        if not state.last_action_success and state.provider == "playwright":
            return result_failed(Intent.COMPARE_THESE_RESULTS, body)
        return result_success(Intent.COMPARE_THESE_RESULTS, body, data={"read_only": True})


class CompareThesePagesAction(BaseAction):
    intent = Intent.COMPARE_THESE_PAGES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import compare_latest_results

        return result_success(Intent.COMPARE_THESE_PAGES, compare_latest_results(), data={"read_only": True})


class WhatTabIsActiveAction(BaseAction):
    intent = Intent.WHAT_TAB_IS_ACTIVE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import active_tab_status

        return result_success(Intent.WHAT_TAB_IS_ACTIVE, active_tab_status(), data={"read_only": True})


class TestRealBrowserAction(BaseAction):
    intent = Intent.TEST_REAL_BROWSER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from browser.runtime import test_real_browser

        ok, body = test_real_browser()
        if not ok:
            return result_failed(Intent.TEST_REAL_BROWSER, body)
        return result_success(Intent.TEST_REAL_BROWSER, body)


class SummarizeMyDayAction(BaseAction):
    intent = Intent.SUMMARIZE_MY_DAY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from providers.daily_summary_provider import get_calendar_provider

        summary = get_calendar_provider().summarize_day()
        return result_success(Intent.SUMMARIZE_MY_DAY, summary.format("Daily summary (mock provider)"), data={"read_only": True})


class SummarizeMyLast100EmailsAction(BaseAction):
    intent = Intent.SUMMARIZE_MY_LAST_100_EMAILS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from providers.daily_summary_provider import get_email_provider

        summary = get_email_provider().summarize_last(100)
        return result_success(
            Intent.SUMMARIZE_MY_LAST_100_EMAILS,
            summary.format("Email summary (mock provider)"),
            data={"read_only": True},
        )


class WhatNeedsMyAttentionTodayAction(BaseAction):
    intent = Intent.WHAT_NEEDS_MY_ATTENTION_TODAY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from providers.daily_summary_provider import get_calendar_provider, get_email_provider

        cal = get_calendar_provider().summarize_day()
        mail = get_email_provider().summarize_last(20)
        lines = [
            "What needs my attention today (mock):",
            "MOCK MODE | NO REAL EXTERNAL ACCESS | SIMULATED OUTPUT ONLY",
            "urgent:",
            *[f"  - {x}" for x in (cal.urgent + mail.urgent)],
            "waiting_on_me:",
            *[f"  - {x}" for x in (cal.waiting_on_me + mail.waiting_on_me)],
            "schedule:",
            *[f"  - {x}" for x in cal.schedule],
            "risks:",
            *[f"  - {x}" for x in (cal.risks + mail.risks)],
            "recommended_actions:",
            *[f"  - {x}" for x in (cal.recommended_actions + mail.recommended_actions)],
        ]
        return result_success(Intent.WHAT_NEEDS_MY_ATTENTION_TODAY, "\n".join(lines), data={"read_only": True})


class FindCalendarConflictsAction(BaseAction):
    intent = Intent.FIND_CALENDAR_CONFLICTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from providers.daily_summary_provider import get_calendar_provider

        summary = get_calendar_provider().find_conflicts()
        return result_success(Intent.FIND_CALENDAR_CONFLICTS, summary.format("Calendar conflicts (mock provider)"), data={"read_only": True})


class ShowCapabilityHealthAction(BaseAction):
    intent = Intent.SHOW_CAPABILITY_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        import config as cfg
        from browser.runtime import get_browser_runtime_state
        from memory.store import get_personal_memory
        from services.runtime_monitor import get_runtime_monitor
        from voice.audio_status import get_audio_status
        from voice.streaming_stt.session_policy import (
            get_streaming_disable_reason,
            is_streaming_stt_enabled_for_session,
        )
        from voice.wake_diagnostics import format_wake_diagnostics

        audio = get_audio_status()
        browser = get_browser_runtime_state()
        mem_count = len(get_personal_memory().list_visible(limit=200))
        runtime_status = get_runtime_monitor().run_once()
        runtime_overall = runtime_status.get("overall", "unknown")

        overlay_health = "unknown"
        try:
            from ui.overlay_app import get_overlay_controller

            snap = get_overlay_controller().health_snapshot()
            overlay_health = "ok" if snap.get("qt_thread_alive") else "degraded"
        except Exception:
            pass

        lines = [
            "Capability health",
            f"  voice_runtime: mode={cfg.VOICE_RUNTIME_MODE or 'default'} conversational={bool(cfg.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED)}",
            f"  streaming_runtime: enabled={is_streaming_stt_enabled_for_session()} cfg={bool(cfg.STT_STREAMING_BUFFER_ENABLED)} disable_reason={get_streaming_disable_reason() or 'none'}",
            f"  tts_backend_verification: {audio.selected_verified_audio_backend or 'unverified'}",
            f"  browser_mode: {browser.provider}",
            f"  memory_health: entries={mem_count}",
            f"  scheduler_health: {runtime_overall}",
            f"  overlay_health: {overlay_health}",
            f"  wakeword_health: {'ok' if 'Wake diagnostics' in format_wake_diagnostics() else 'unknown'}",
        ]
        return result_success(Intent.SHOW_CAPABILITY_HEALTH, "\n".join(lines), data={"read_only": True})

