"""Intent → agent routing table (Phase 70)."""

from __future__ import annotations

from core.types import Intent

from agents.base import AgentId

# Prefix / exact intent value → owning agent (first match wins)
_INTENT_PREFIX_RULES: tuple[tuple[str, AgentId], ...] = (
    ("show_voice", AgentId.CONVERSATION),
    ("test_voice", AgentId.CONVERSATION),
    ("test_tts", AgentId.CONVERSATION),
    ("test_direct_tts", AgentId.CONVERSATION),
    ("test_streaming_stt", AgentId.CONVERSATION),
    ("test_real_voice", AgentId.CONVERSATION),
    ("show_audio", AgentId.CONVERSATION),
    ("show_wake", AgentId.CONVERSATION),
    ("calibrate_voice", AgentId.CONVERSATION),
    ("diagnose_voice", AgentId.CONVERSATION),
    ("benchmark_stt", AgentId.CONVERSATION),
    ("show_stt", AgentId.CONVERSATION),
    ("show_tts", AgentId.CONVERSATION),
    ("tool_mode", AgentId.CONVERSATION),
    ("cancel_active_speech", AgentId.CONVERSATION),
    ("show_conversation", AgentId.CONVERSATION),
    ("remember", AgentId.MEMORY),
    ("forget_memory", AgentId.MEMORY),
    ("forget_preference", AgentId.MEMORY),
    ("search_memory", AgentId.MEMORY),
    ("show_memory", AgentId.MEMORY),
    ("list_memory", AgentId.MEMORY),
    ("index_project", AgentId.MEMORY),
    ("search_project_knowledge", AgentId.MEMORY),
    ("repair_memory", AgentId.MEMORY),
    ("set_alias", AgentId.MEMORY),
    ("delete_alias", AgentId.MEMORY),
    ("list_aliases", AgentId.MEMORY),
    ("set_preference", AgentId.MEMORY),
    ("list_preferences", AgentId.MEMORY),
    ("summarize_session", AgentId.MEMORY),
    ("what_were_we_doing", AgentId.MEMORY),
    # ── Browser intents → AgentId.BROWSER (S3.2) ───────────────────────────
    ("open_browser", AgentId.BROWSER),
    ("open_website", AgentId.BROWSER),
    ("search_web", AgentId.BROWSER),
    ("find_information", AgentId.BROWSER),
    ("summarize_this_page", AgentId.BROWSER),
    ("summarize_current", AgentId.BROWSER),
    ("what_tab", AgentId.BROWSER),
    ("browser", AgentId.BROWSER),
    # ── Desktop intents → AgentId.DESKTOP (S3.3) ────────────────────────────
    ("open_app", AgentId.DESKTOP),
    ("what_is_on_my_screen", AgentId.DESKTOP),
    ("summarize_this_screen", AgentId.DESKTOP),
    ("click_button", AgentId.DESKTOP),
    ("type_this", AgentId.DESKTOP),
    ("list_open_windows", AgentId.DESKTOP),
    ("switch_to_chrome", AgentId.DESKTOP),
    ("show_desktop", AgentId.DESKTOP),
    ("desktop", AgentId.DESKTOP),
    ("focus_window", AgentId.DESKTOP),
    ("mouse_", AgentId.DESKTOP),
    ("discover_apps", AgentId.DESKTOP),
    ("list_apps", AgentId.DESKTOP),
    ("approve_app", AgentId.DESKTOP),
    ("forget_app", AgentId.DESKTOP),
    ("describe_screen", AgentId.DESKTOP),
    ("read_screen", AgentId.DESKTOP),
    ("take_screenshot", AgentId.DESKTOP),
    ("find_on_screen", AgentId.DESKTOP),
    # ── Phase 72 tool use ───────────────────────────────────────────────────
    # run_tool_task is health-gated via BROWSER (if the browser subsystem is
    # down we must not execute). plan/show are read-only and routed to EXECUTIVE
    # so they remain available even when the browser is unhealthy.
    ("run_tool_task", AgentId.BROWSER),
    ("plan_tool_task", AgentId.EXECUTIVE),
    ("show_last_tool_run", AgentId.EXECUTIVE),
    # ── Trading intents → AgentId.TRADING (S3.4) ────────────────────────────
    ("run_live", AgentId.TRADING),
    ("open_trading_dashboard", AgentId.TRADING),
    ("show_dashboard_health", AgentId.TRADING),
    ("enable_kill_switch", AgentId.TRADING),
    ("disable_kill_switch", AgentId.TRADING),
    ("show_open_positions", AgentId.TRADING),
    ("show_last_errors", AgentId.TRADING),
    ("show_rejection_reasons", AgentId.TRADING),
    ("search_trading", AgentId.TRADING),
    ("trading_", AgentId.TRADING),
    ("investigate", AgentId.RESEARCH),
    ("compare_live", AgentId.RESEARCH),
    ("compare_backtest", AgentId.RESEARCH),
    ("compare_these", AgentId.RESEARCH),
    ("summarize_my_inbox", AgentId.RESEARCH),
    ("summarize_my_calendar", AgentId.RESEARCH),
    ("summarize_my_day", AgentId.RESEARCH),
    ("show_urgent_emails", AgentId.RESEARCH),
    ("find_calendar", AgentId.RESEARCH),
    ("build_investigation", AgentId.RESEARCH),
    ("propose_investigation", AgentId.RESEARCH),
    ("run_deep_review", AgentId.RESEARCH),
    ("explain_latest_error", AgentId.CODING),
    ("find_failing_tests", AgentId.CODING),
    ("review_latest_patch", AgentId.CODING),
    ("explain_this_error", AgentId.CODING),
    ("find_function", AgentId.CODING),
    ("find_class", AgentId.CODING),
    ("search_code", AgentId.CODING),
    ("search_project_file", AgentId.CODING),
    ("inspect_project", AgentId.CODING),
    ("apply_task_patch", AgentId.CODING),
    ("propose_task_patch", AgentId.CODING),
    ("rollback_task_patch", AgentId.CODING),
    ("show_task_patch", AgentId.CODING),
    ("start_task", AgentId.PLANNING),
    ("stop_task", AgentId.PLANNING),
    ("show_task", AgentId.PLANNING),
    ("approve_task", AgentId.PLANNING),
    ("run_task_step", AgentId.PLANNING),
    ("queue_task", AgentId.PLANNING),
    ("plan_experiments", AgentId.PLANNING),
    ("assistant_plan", AgentId.PLANNING),
    ("run_workflow", AgentId.PLANNING),
    ("list_workflows", AgentId.PLANNING),
    ("start_trading_workspace", AgentId.PLANNING),
    ("start_study_workspace", AgentId.PLANNING),
    ("start_dev_workspace", AgentId.PLANNING),
)

_EXACT_INTENT_AGENTS: dict[str, AgentId] = {
    Intent.UNKNOWN.value: AgentId.EXECUTIVE,
    Intent.CLARIFY.value: AgentId.EXECUTIVE,
    Intent.SHOW_CAPABILITIES.value: AgentId.EXECUTIVE,
    Intent.SHOW_SYSTEM_HEALTH.value: AgentId.EXECUTIVE,
    Intent.SHOW_JARVIS_STATUS.value: AgentId.EXECUTIVE,
    Intent.ALPHA_SETUP_CHECK.value: AgentId.EXECUTIVE,
    Intent.SHOW_ALPHA_REPORT.value: AgentId.EXECUTIVE,
    Intent.GENERATE_PRODUCT_READINESS_REPORT.value: AgentId.EXECUTIVE,
}


def agent_for_intent(intent: Intent | str) -> AgentId:
    """Resolve owning agent for an intent (used by runtime_wiring at execute time)."""
    value = intent.value if isinstance(intent, Intent) else str(intent)
    if value in _EXACT_INTENT_AGENTS:
        return _EXACT_INTENT_AGENTS[value]
    for prefix, agent in _INTENT_PREFIX_RULES:
        if value.startswith(prefix) or prefix in value:
            return agent
    return AgentId.EXECUTIVE
