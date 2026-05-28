"""Central configuration for local_jarvis."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

# Project roots
PROJECT_ROOT = Path(__file__).resolve().parent
JARVIS_WEBSITE_PROJECT_ROOT = Path(
    os.getenv("JARVIS_WEBSITE_PROJECT_ROOT", r"C:\jarvis website")
).expanduser()
_ENV_PATH = PROJECT_ROOT / ".env"

from core.env_precedence import load_project_env  # noqa: E402

load_project_env(_ENV_PATH)
DATA_DIR = PROJECT_ROOT / "data"
APPROVED_APPS_PATH = DATA_DIR / "approved_apps.json"
APPROVED_WEBSITES_PATH = DATA_DIR / "approved_websites.json"
MEMORY_PATH = DATA_DIR / "memory.json"
MEMORY_STORE_PATH = DATA_DIR / "memory_store.json"
PROJECT_INDEX_PATH = DATA_DIR / "project_index.json"
MEMORY_ENABLED = os.getenv("MEMORY_ENABLED", "true").lower() in {"1", "true", "yes"}
PROJECT_INDEXING_ENABLED = os.getenv("PROJECT_INDEXING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
PROJECT_INDEX_MAX_FILE_KB = int(os.getenv("PROJECT_INDEX_MAX_FILE_KB", "512"))
PREFERENCES_PATH = DATA_DIR / "preferences.json"
ALIASES_PATH = DATA_DIR / "aliases.json"
BACKUPS_DIR = DATA_DIR / "backups"
COMMAND_HISTORY_PATH = DATA_DIR / "command_history.jsonl"
SETTINGS_PATH = DATA_DIR / "settings.json"
SESSION_STATE_PATH = DATA_DIR / "session_state.json"
VOICE_CALIBRATION_PATH = DATA_DIR / "voice_calibration.json"

# Trading project
TRADING_PROJECT_ROOT = Path(
    os.getenv("TRADING_PROJECT_ROOT", r"C:\FINAL_ALGO_TRADER")
)
TRADING_DASHBOARD_SCRIPT = (
    TRADING_PROJECT_ROOT / "tools" / "trading_dashboard" / "run_dashboard.ps1"
)
TRADING_DAILY_LOOP_SCRIPT = (
    TRADING_PROJECT_ROOT / "scripts" / "run_live_daily.ps1"
)
TRADING_WEEKLY_LOOP_SCRIPT = (
    TRADING_PROJECT_ROOT / "scripts" / "run_live_weekly.ps1"
)
TRADING_REPORTS_ROOT = TRADING_PROJECT_ROOT / "reports" / "live_paper"
TRADING_REPORTS_DUAL = TRADING_PROJECT_ROOT / "reports" / "live_paper" / "dual"
TRADING_REPORTS_STATE = TRADING_PROJECT_ROOT / "reports" / "live_paper" / "state"
TRADING_REPORTS_LOGS = (
    TRADING_PROJECT_ROOT / "reports" / "live_paper" / "scheduled_logs"
)

# Trading dashboard (fixed localhost URL only — no arbitrary browser targets)
ALLOWED_TRADING_DASHBOARD_URL = "http://127.0.0.1:8077"


def _resolve_trading_dashboard_url(raw: str) -> str:
    candidate = (raw or ALLOWED_TRADING_DASHBOARD_URL).strip()
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme == "http"
        and host in ("127.0.0.1", "localhost")
        and parsed.port == 8077
        and (parsed.path or "") in ("", "/")
    ):
        return ALLOWED_TRADING_DASHBOARD_URL
    return ALLOWED_TRADING_DASHBOARD_URL


_TRADING_DASHBOARD_URL_RAW = os.getenv(
    "TRADING_DASHBOARD_URL", ALLOWED_TRADING_DASHBOARD_URL
).strip()
TRADING_DASHBOARD_URL = _resolve_trading_dashboard_url(_TRADING_DASHBOARD_URL_RAW)

# Dashboard health endpoints
DASHBOARD_HEALTH_URL = os.getenv(
    "DASHBOARD_HEALTH_URL", "http://127.0.0.1:8077/api/health"
)
DASHBOARD_SUMMARY_URL = os.getenv(
    "DASHBOARD_SUMMARY_URL",
    "http://127.0.0.1:8077/api/control/dashboard-summary",
)

# Log scanning limits
LOG_SCAN_MAX_FILES = int(os.getenv("LOG_SCAN_MAX_FILES", "20"))
LOG_SCAN_MAX_BYTES = int(os.getenv("LOG_SCAN_MAX_BYTES", str(2 * 1024 * 1024)))
LOG_TAIL_LINES = int(os.getenv("LOG_TAIL_LINES", "200"))

# Code search
CODE_SEARCH_MAX_RESULTS = int(os.getenv("CODE_SEARCH_MAX_RESULTS", "40"))
CODE_SEARCH_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
        "cache",
        "dist",
        "build",
    }
)
CODE_SEARCH_EXTENSIONS = frozenset(
    {".py", ".ps1", ".js", ".ts", ".html", ".css", ".json", ".md", ".yaml", ".yml"}
)

# Application executables (Windows defaults)
CURSOR_EXE = Path(
    os.getenv(
        "CURSOR_EXE",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe"),
    )
)
CHROME_EXE = Path(
    os.getenv(
        "CHROME_EXE",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
)

# Allowlisted PowerShell scripts (hardcoded paths only)
ALLOWED_POWERSHELL_SCRIPTS: frozenset[Path] = frozenset(
    {
        TRADING_DASHBOARD_SCRIPT,
        TRADING_DAILY_LOOP_SCRIPT,
        TRADING_WEEKLY_LOOP_SCRIPT,
    }
)

# Router
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
CONFIRMATION_TIMEOUT_SECONDS = int(os.getenv("CONFIRMATION_TIMEOUT_SECONDS", "120"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TOOL_FIRST_MODE = os.getenv("TOOL_FIRST_MODE", "true").lower() in {"1", "true", "yes"}

# All intents that may be routed (allowlist)
ALLOWED_INTENTS: frozenset[str] = frozenset(
    {
        "open_cursor",
        "open_chrome",
        "open_file_explorer",
        "open_terminal",
        "open_task_manager",
        "open_trading_dashboard",
        "open_trading_dashboard_url",
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "stop_trading_loop",
        "show_latest_live_report",
        "show_open_positions",
        "show_last_errors",
        "show_dashboard_health",
        "show_recent_trading_history",
        "show_rejection_reasons",
        "show_blocked_trades",
        "search_trading_logs",
        "enable_kill_switch",
        "disable_kill_switch",
        "open_project_folder",
        "open_latest_log",
        "summarize_latest_log",
        "search_project_file_by_name",
        "search_code_text",
        "find_function",
        "find_class",
        "find_config_key",
        "find_risk_usage",
        "find_delayed_entry_logic",
        "find_execution_events_logic",
        "show_cpu_ram_usage",
        "show_disk_usage",
        "show_network_status",
        "show_system_status",
        "show_stt_status",
        "benchmark_stt",
        "show_tts_status",
        "show_tts_debug",
        "test_tts_playback",
        "test_direct_tts",
        "test_streaming_stt",
        "show_voice_debug",
        "show_audio_status",
        "tool_mode_status",
        "test_voice_output",
        "show_wake_diagnostics",
        "show_audio_devices",
        "test_left_channel",
        "test_right_channel",
        "test_audio_routing",
        "cycle_audio_output",
        "show_windows_audio_routing",
        "cycle_windows_playback_target",
        "stop_speech_hard",
        "calibrate_voice",
        "diagnose_voice_runtime",
        "reset_jarvis_runtime",
        "show_runtime_status",
        "show_latency_status",
        "show_voice_performance_status",
        "shutdown_jarvis",
        "show_capabilities",
        "list_skills",
        "explain_skill",
        "help_for_command",
        "remember_preference",
        "remember_fact",
        "forget_memory",
        "list_memory",
        "search_memory",
        "remember_this",
        "show_memory",
        "index_project",
        "search_project_knowledge",
        "show_memory_graph",
        "search_memory_graph",
        "set_alias",
        "delete_alias",
        "list_aliases",
        "set_preference",
        "list_preferences",
        "forget_preference",
        "describe_screen",
        "read_screen_text",
        "analyze_active_window",
        "find_on_screen",
        "detect_screen_errors",
        "get_active_window",
        "take_screenshot",
        "list_visible_windows",
        "run_diagnostics",
        "diagnose_dashboard",
        "diagnose_trading_loop",
        "diagnose_recent_errors",
        "analyze_current_screen",
        "explain_last_failure",
        "suggest_next_steps",
        "list_workflows",
        "run_workflow",
        "explain_workflow",
        "enable_autostart",
        "disable_autostart",
        "show_autostart_status",
        "run_jarvis_health_check",
        "show_watchdog_status",
        "get_focused_app",
        "list_windows_detailed",
        "get_clipboard_summary",
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
        "discover_apps",
        "list_apps",
        "search_apps",
        "open_app",
        "approve_app",
        "forget_app",
        "list_websites",
        "open_website",
        "open_browser",
        "approve_website",
        "forget_website",
        "start_task",
        "show_task_plan",
        "approve_task_plan",
        "run_task_step",
        "stop_task",
        "show_task_status",
        "show_task_report",
        "show_task_findings",
        "propose_task_patch",
        "show_task_patch",
        "approve_task_patch",
        "reject_task_patch",
        "apply_task_patch",
        "rollback_task_patch",
        "show_last_diff",
        "review_trading_algorithm",
        "compare_backtest_to_paper",
        "find_live_backtest_mismatch",
        "generate_backtest_paper_report",
        "plan_experiments",
        "queue_task",
        "show_task_queue",
        "pause_task_queue",
        "resume_task_queue",
        "start_trading_workspace",
        "start_study_workspace",
        "start_dev_workspace",
        "suggest_ui_click",
        "confirm_ui_click",
        "browser_dom_read",
        "build_presentation",
        "create_report_document",
        "show_startup_health",
        "show_settings_status",
        "show_jarvis_status",
        "show_command_audit",
        "show_approvals",
        "approve_pending_action",
        "reject_pending_action",
        "clear_approvals",
        "show_overlay",
        "hide_overlay",
        "toggle_quiet_mode",
        "what_am_i_doing",
        "review_latest_patch",
        "summarize_recent_changes",
        "show_failing_tests",
        "summarize_this_file",
        "show_recent_commands",
        "explain_this_error",
        "start_study_mode",
        "focus_mode",
        "summarize_my_notes",
        "explain_this_code",
        "quiz_me",
        "what_should_i_study_next",
        "assistant_explain",
        "assistant_plan",
        "what_were_we_doing",
        "summarize_session",
        "switch_voice",
        "list_voices",
        "set_female_voice",
        "set_cinematic_voice",
        "set_voice_emotion",
        "benchmark_tts",
        "stop_speaking",
        "list_stt_engines",
        "show_stt_stack_status",
        "auto_tune_voice",
        "test_direct_speech",
        "verify_direct_speech_backend",
        "force_verified_direct_speech",
        "test_normal_speech",
        "audio_route_prove",
        "force_direct_pyttsx3_normal_mode",
        "test_subprocess_speech",
        "force_shell_tts_test",
        "voice_smoke_test",
        "voice_smoke_test",
        "foundation_health_check",
        "show_launcher_status",
        "show_runtime_threads",
        "show_control_status",
        "show_screen_status",
        "benchmark_voice_modes",
        "show_tts_threads",
        "phase45_status",
        "phase46_status",
        "inspect_project",
        "inspect_website_project",
        "show_memory_debug",
        "show_browser_debug",
        "search_web_for",
        "find_information_about",
        "open_best_result",
        "summarize_top_results",
        "compare_these_search_results",
        "extract_key_facts_from_this_page",
        "save_browser_research_report",
        "what_is_on_my_screen",
        "summarize_this_screen",
        "click_button_that_says",
        "type_this",
        "switch_to_chrome",
        "list_open_windows",
        "show_voice_health",
        "repair_memory_store",
        "show_browser_health",
        "show_desktop_operator_health",
        "show_system_health",
        "show_performance_report",
        "summarize_my_inbox",
        "show_urgent_emails",
        "summarize_my_calendar",
        "generate_product_readiness_report",
        "summarize_this_page",
        "compare_these_results",
        "compare_these_pages",
        "what_tab_is_active",
        "test_real_browser",
        "test_real_voice_conversation",
        "show_desktop_vision_health",
        "alpha_setup_check",
        "show_alpha_report",
        "summarize_my_day",
        "summarize_my_last_100_emails",
        "what_needs_my_attention_today",
        "find_calendar_conflicts",
        "summarize_current_project",
        "find_failing_tests",
        "explain_latest_error",
        "investigate_trading_mismatch",
        "compare_live_vs_backtest",
        "inspect_latest_live_report",
        "inspect_latest_backtest_report",
        "find_recent_code_changes",
        "propose_investigation_plan",
        "run_safe_diagnostics",
        "generate_findings_report",
        "build_investigation_graph",
        "show_investigation_graph",
        "search_investigation_graph",
        "trace_algorithm_behavior",
        "diff_live_backtest_logic",
        "hunt_algorithm_bugs",
        "propose_algorithm_patch",
        "plan_verification_run",
        "replay_symbol",
        "replay_latest_signal",
        "replay_live_vs_backtest",
        "verify_top_hypothesis",
        "verify_all_hypotheses",
        "show_replay_timeline",
        "show_replay_diff",
        "build_verification_fixture",
        "export_replay_snapshot",
        "trace_signal_lifecycle",
        "trace_execution_lifecycle",
        "show_causality_graph",
        "investigation_confidence_report",
        "simulate_patch_top_hypothesis",
        "run_patch_simulation",
        "compare_replay_before_after",
        "estimate_patch_impact",
        "generate_patch_simulation_report",
        "show_patch_simulation",
        "approve_patch_apply",
        "reject_patch_apply",
        "run_historical_validation_sweep",
        "show_validation_sweep",
        "export_validation_sweep",
        "compare_strategy_metrics_before_after",
        "show_worst_divergence_symbols",
        "estimate_production_risk",
        "recommend_production_action",
        "show_investigation_summary",
        "audit_price_integrity",
        "compare_candle_sources",
        "trace_price_source",
        "find_close_price_mismatches",
        "inspect_data_cache_drift",
        "check_timestamp_alignment",
        "check_adjusted_price_usage",
        "check_duplicate_bars",
        "generate_price_integrity_report",
        "audit_execution_path",
        "explain_zero_execution_attempts",
        "trace_signal_to_order",
        "show_execution_blockers",
        "rank_execution_block_reasons",
        "inspect_execution_adapter",
        "compare_signal_count_to_order_attempts",
        "generate_execution_investigation_report",
        "trace_signal_to_execution",
        "trace_blocked_signal",
        "explain_top_execution_blocker",
        "reconstruct_execution_flow",
        "show_signal_lifecycle_timeline",
        "rank_dead_signal_causes",
        "simulate_unblock_scenario",
        "propose_execution_fix",
        "generate_execution_flow_report",
        "simulate_execution_cleanup_patch",
        "compare_risk_before_after_cleanup",
        "show_stale_open_positions",
        "propose_execution_cleanup_patch",
        "generate_execution_cleanup_report",
        "show_approved_patch",
        "validate_patch_safety",
        "apply_approved_patch",
        "rollback_last_patch",
        "show_patch_history",
        "validate_applied_patch",
        "replay_after_patch",
        "compare_pre_post_patch",
        "run_patch_workflow",
        "show_patch_workflow_status",
        "show_runtime_health",
        "show_healing_actions",
        "show_stuck_workers",
        "restart_failed_worker",
        "clear_stale_locks",
        "recover_overlay",
        "recover_voice_system",
        "restart_dashboard",
        "restart_wake_listener",
        "restart_operator_console",
        "validate_runtime_integrity",
        "phase49_status",
        "what_am_i_looking_at",
        "summarize_current_screen",
        "summarize_trading_health",
        "explain_why_no_trades_today",
        "compare_today_vs_yesterday",
        "show_top_operational_blockers",
        "show_current_execution_risk",
        "summarize_live_engine_status",
        "resume_last_task",
        "show_recent_investigations",
        "continue_investigation",
        "open_last_report",
        "search_reports",
        "show_current_state",
        "show_active_systems",
        "show_runtime_summary",
        "show_operational_suggestions",
        "phase50_status",
        "show_open_windows",
        "show_screen_system_status",
        "show_focused_window",
        "switch_to_browser",
        "switch_to_cursor",
        "switch_to_dashboard",
        "focus_terminal",
        "show_memory_state",
        "clear_completed_task",
        "pin_investigation",
        "continue_trading_investigation",
        "show_trading_operations_dashboard",
        "show_running_tasks",
        "cancel_task",
        "show_completed_tasks",
        "show_failed_tasks",
        "rerun_last_background_task",
        "show_recent_results",
        "show_notifications",
        "clear_notifications",
        "explain_last_result",
        "reopen_task_result",
        "archive_notification",
        "explain_notification",
        "continue_previous_session",
        "summarize_unresolved_issues",
        "resume_latest_investigation",
        "what_changed_since_last_session",
        "summarize_system_intelligence",
        "summarize_unresolved_blockers",
        "explain_current_operational_state",
        "recommend_next_action",
        "what_should_we_investigate_next",
        "show_investigation_schedule",
        "run_investigation_cycle",
        "pause_investigation_loop",
        "resume_investigation_loop",
        "run_nightly_investigation_now",
        "show_blocker_trends",
        "compare_blocker_trends",
        "explain_dominant_blocker",
        "show_blocker_history",
        "cluster_replay_divergences",
        "show_divergence_clusters",
        "explain_largest_divergence_cluster",
        "show_active_hypotheses",
        "verify_active_hypotheses",
        "explain_autonomous_top_hypothesis",
        "compare_hypothesis_history",
        "show_intelligence_timeline",
        "explain_recent_anomalies",
        "compare_today_vs_yesterday_intelligence",
        "summarize_autonomous_findings",
        "summarize_operational_anomalies",
        "explain_current_trading_risk",
        "show_verification_plans",
        "explain_verification_plan",
        "run_verification_plan",
        "verify_root_causes",
        "show_confidence_evolution",
        "explain_confidence_changes",
        "compare_root_cause_confidence",
        "show_contradictory_evidence",
        "explain_contradiction",
        "resolve_contradiction",
        "suggest_experiments",
        "explain_experiment_impact",
        "run_safe_experiment_simulation",
        "show_root_cause_graph",
        "explain_root_cause_graph",
        "trace_causal_chain",
        "summarize_root_causes",
        "explain_dominant_root_cause",
        "explain_operational_failures",
        "summarize_verified_findings",
        "explain_why_trades_are_blocked",
        "compare_operational_periods",
        "compare_before_after_cleanup",
        "compare_investigation_periods",
        "what_are_we_discussing",
        "summarize_current_conversation",
        "resume_previous_topic",
        "show_conversation_state",
        "start_continuous_listening",
        "stop_continuous_listening",
        "explain_this_project",
        "prepare_investor_summary",
        "explain_architecture",
        "generate_project_roadmap",
        "show_project_intelligence",
        "propose_engineering_patch",
        "simulate_engineering_patch",
        "validate_engineering_patch",
        "explain_patch_risks",
        "show_proactive_suggestions",
        "show_realtime_runtime",
        "phase56_status",
        "show_voice_latency",
        "phase57_status",
        "test_realtime_voice",
        "test_interrupt_speech",
        "show_realtime_provider_status",
        "benchmark_realtime_providers",
        "show_realtime_latency_breakdown",
        "test_websocket_realtime_voice",
        "benchmark_realtime_streaming",
        "show_runtime_config_sources",
        "show_runtime_config_mismatches",
        "show_capability_health",
        "show_conversation_runtime",
        "show_interruption_metrics",
        "show_conversational_memory",
        "benchmark_full_duplex_conversation",
        "phase59_status",
        "cancel_active_speech",
        "unknown",
        "clarify",
    }
)

# Intents with registered handlers (Phase 1.5)
IMPLEMENTED_INTENTS: frozenset[str] = frozenset(
    {
        "open_cursor",
        "open_chrome",
        "open_trading_dashboard",
        "open_trading_dashboard_url",
        "open_terminal",
        "open_project_folder",
        "open_latest_log",
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "show_latest_live_report",
        "show_open_positions",
        "show_last_errors",
        "show_dashboard_health",
        "show_recent_trading_history",
        "show_rejection_reasons",
        "show_blocked_trades",
        "search_trading_logs",
        "summarize_latest_log",
        "search_project_file_by_name",
        "search_code_text",
        "find_function",
        "find_class",
        "find_config_key",
        "find_risk_usage",
        "find_delayed_entry_logic",
        "find_execution_events_logic",
        "show_system_status",
        "show_stt_status",
        "benchmark_stt",
        "show_tts_status",
        "show_tts_debug",
        "test_tts_playback",
        "test_direct_tts",
        "test_streaming_stt",
        "show_voice_debug",
        "show_audio_status",
        "tool_mode_status",
        "test_voice_output",
        "show_wake_diagnostics",
        "show_audio_devices",
        "test_left_channel",
        "test_right_channel",
        "test_audio_routing",
        "cycle_audio_output",
        "show_windows_audio_routing",
        "cycle_windows_playback_target",
        "stop_speech_hard",
        "calibrate_voice",
        "diagnose_voice_runtime",
        "reset_jarvis_runtime",
        "show_runtime_status",
        "show_latency_status",
        "show_voice_performance_status",
        "phase45_status",
        "phase46_status",
        "inspect_project",
        "inspect_website_project",
        "show_memory_debug",
        "show_browser_debug",
        "search_web_for",
        "find_information_about",
        "open_best_result",
        "summarize_top_results",
        "compare_these_search_results",
        "extract_key_facts_from_this_page",
        "save_browser_research_report",
        "what_is_on_my_screen",
        "summarize_this_screen",
        "click_button_that_says",
        "type_this",
        "switch_to_chrome",
        "list_open_windows",
        "show_voice_health",
        "repair_memory_store",
        "show_browser_health",
        "show_desktop_operator_health",
        "show_system_health",
        "show_performance_report",
        "summarize_my_inbox",
        "show_urgent_emails",
        "summarize_my_calendar",
        "generate_product_readiness_report",
        "summarize_this_page",
        "compare_these_results",
        "compare_these_pages",
        "what_tab_is_active",
        "test_real_browser",
        "test_real_voice_conversation",
        "show_desktop_vision_health",
        "alpha_setup_check",
        "show_alpha_report",
        "summarize_my_day",
        "summarize_my_last_100_emails",
        "what_needs_my_attention_today",
        "find_calendar_conflicts",
        "summarize_current_project",
        "find_failing_tests",
        "explain_latest_error",
        "investigate_trading_mismatch",
        "compare_live_vs_backtest",
        "inspect_latest_live_report",
        "inspect_latest_backtest_report",
        "find_recent_code_changes",
        "propose_investigation_plan",
        "run_safe_diagnostics",
        "generate_findings_report",
        "build_investigation_graph",
        "show_investigation_graph",
        "search_investigation_graph",
        "trace_algorithm_behavior",
        "diff_live_backtest_logic",
        "hunt_algorithm_bugs",
        "propose_algorithm_patch",
        "plan_verification_run",
        "replay_symbol",
        "replay_latest_signal",
        "replay_live_vs_backtest",
        "verify_top_hypothesis",
        "verify_all_hypotheses",
        "show_replay_timeline",
        "show_replay_diff",
        "build_verification_fixture",
        "export_replay_snapshot",
        "trace_signal_lifecycle",
        "trace_execution_lifecycle",
        "show_causality_graph",
        "investigation_confidence_report",
        "simulate_patch_top_hypothesis",
        "run_patch_simulation",
        "compare_replay_before_after",
        "estimate_patch_impact",
        "generate_patch_simulation_report",
        "show_patch_simulation",
        "approve_patch_apply",
        "reject_patch_apply",
        "run_historical_validation_sweep",
        "show_validation_sweep",
        "export_validation_sweep",
        "compare_strategy_metrics_before_after",
        "show_worst_divergence_symbols",
        "estimate_production_risk",
        "recommend_production_action",
        "show_investigation_summary",
        "audit_price_integrity",
        "compare_candle_sources",
        "trace_price_source",
        "find_close_price_mismatches",
        "inspect_data_cache_drift",
        "check_timestamp_alignment",
        "check_adjusted_price_usage",
        "check_duplicate_bars",
        "generate_price_integrity_report",
        "audit_execution_path",
        "explain_zero_execution_attempts",
        "trace_signal_to_order",
        "show_execution_blockers",
        "rank_execution_block_reasons",
        "inspect_execution_adapter",
        "compare_signal_count_to_order_attempts",
        "generate_execution_investigation_report",
        "trace_signal_to_execution",
        "trace_blocked_signal",
        "explain_top_execution_blocker",
        "reconstruct_execution_flow",
        "show_signal_lifecycle_timeline",
        "rank_dead_signal_causes",
        "simulate_unblock_scenario",
        "propose_execution_fix",
        "generate_execution_flow_report",
        "simulate_execution_cleanup_patch",
        "compare_risk_before_after_cleanup",
        "show_stale_open_positions",
        "propose_execution_cleanup_patch",
        "generate_execution_cleanup_report",
        "show_approved_patch",
        "validate_patch_safety",
        "apply_approved_patch",
        "rollback_last_patch",
        "show_patch_history",
        "validate_applied_patch",
        "replay_after_patch",
        "compare_pre_post_patch",
        "run_patch_workflow",
        "show_patch_workflow_status",
        "show_runtime_health",
        "show_healing_actions",
        "show_stuck_workers",
        "restart_failed_worker",
        "clear_stale_locks",
        "recover_overlay",
        "recover_voice_system",
        "restart_dashboard",
        "restart_wake_listener",
        "restart_operator_console",
        "validate_runtime_integrity",
        "phase49_status",
        "what_am_i_looking_at",
        "summarize_current_screen",
        "summarize_trading_health",
        "explain_why_no_trades_today",
        "compare_today_vs_yesterday",
        "show_top_operational_blockers",
        "show_current_execution_risk",
        "summarize_live_engine_status",
        "resume_last_task",
        "show_recent_investigations",
        "continue_investigation",
        "open_last_report",
        "search_reports",
        "show_current_state",
        "show_active_systems",
        "show_runtime_summary",
        "show_operational_suggestions",
        "phase50_status",
        "show_open_windows",
        "show_screen_system_status",
        "show_focused_window",
        "switch_to_browser",
        "switch_to_cursor",
        "switch_to_dashboard",
        "focus_terminal",
        "show_memory_state",
        "clear_completed_task",
        "pin_investigation",
        "continue_trading_investigation",
        "show_trading_operations_dashboard",
        "show_running_tasks",
        "cancel_task",
        "show_completed_tasks",
        "show_failed_tasks",
        "rerun_last_background_task",
        "show_recent_results",
        "show_notifications",
        "clear_notifications",
        "explain_last_result",
        "reopen_task_result",
        "archive_notification",
        "explain_notification",
        "continue_previous_session",
        "summarize_unresolved_issues",
        "resume_latest_investigation",
        "what_changed_since_last_session",
        "summarize_system_intelligence",
        "summarize_unresolved_blockers",
        "explain_current_operational_state",
        "recommend_next_action",
        "what_should_we_investigate_next",
        "show_investigation_schedule",
        "run_investigation_cycle",
        "pause_investigation_loop",
        "resume_investigation_loop",
        "run_nightly_investigation_now",
        "show_blocker_trends",
        "compare_blocker_trends",
        "explain_dominant_blocker",
        "show_blocker_history",
        "cluster_replay_divergences",
        "show_divergence_clusters",
        "explain_largest_divergence_cluster",
        "show_active_hypotheses",
        "verify_active_hypotheses",
        "explain_autonomous_top_hypothesis",
        "compare_hypothesis_history",
        "show_intelligence_timeline",
        "explain_recent_anomalies",
        "compare_today_vs_yesterday_intelligence",
        "summarize_autonomous_findings",
        "summarize_operational_anomalies",
        "explain_current_trading_risk",
        "show_verification_plans",
        "explain_verification_plan",
        "run_verification_plan",
        "verify_root_causes",
        "show_confidence_evolution",
        "explain_confidence_changes",
        "compare_root_cause_confidence",
        "show_contradictory_evidence",
        "explain_contradiction",
        "resolve_contradiction",
        "suggest_experiments",
        "explain_experiment_impact",
        "run_safe_experiment_simulation",
        "show_root_cause_graph",
        "explain_root_cause_graph",
        "trace_causal_chain",
        "summarize_root_causes",
        "explain_dominant_root_cause",
        "explain_operational_failures",
        "summarize_verified_findings",
        "explain_why_trades_are_blocked",
        "compare_operational_periods",
        "compare_before_after_cleanup",
        "compare_investigation_periods",
        "what_are_we_discussing",
        "summarize_current_conversation",
        "resume_previous_topic",
        "show_conversation_state",
        "start_continuous_listening",
        "stop_continuous_listening",
        "explain_this_project",
        "prepare_investor_summary",
        "explain_architecture",
        "generate_project_roadmap",
        "show_project_intelligence",
        "propose_engineering_patch",
        "simulate_engineering_patch",
        "validate_engineering_patch",
        "explain_patch_risks",
        "show_proactive_suggestions",
        "show_realtime_runtime",
        "phase56_status",
        "show_voice_latency",
        "phase57_status",
        "test_realtime_voice",
        "test_interrupt_speech",
        "show_realtime_provider_status",
        "benchmark_realtime_providers",
        "show_realtime_latency_breakdown",
        "test_websocket_realtime_voice",
        "benchmark_realtime_streaming",
        "show_runtime_config_sources",
        "show_runtime_config_mismatches",
        "show_capability_health",
        "show_conversation_runtime",
        "show_interruption_metrics",
        "show_conversational_memory",
        "benchmark_full_duplex_conversation",
        "phase59_status",
        "cancel_active_speech",
        "show_disk_usage",
        "show_network_status",
        "shutdown_jarvis",
        "show_capabilities",
        "list_skills",
        "explain_skill",
        "help_for_command",
        "remember_preference",
        "remember_fact",
        "forget_memory",
        "list_memory",
        "search_memory",
        "remember_this",
        "show_memory",
        "index_project",
        "search_project_knowledge",
        "show_memory_graph",
        "search_memory_graph",
        "set_alias",
        "delete_alias",
        "list_aliases",
        "set_preference",
        "list_preferences",
        "forget_preference",
        "describe_screen",
        "read_screen_text",
        "analyze_active_window",
        "find_on_screen",
        "detect_screen_errors",
        "get_active_window",
        "take_screenshot",
        "list_visible_windows",
        "run_diagnostics",
        "diagnose_dashboard",
        "diagnose_trading_loop",
        "diagnose_recent_errors",
        "analyze_current_screen",
        "explain_last_failure",
        "suggest_next_steps",
        "list_workflows",
        "run_workflow",
        "explain_workflow",
        "enable_autostart",
        "disable_autostart",
        "show_autostart_status",
        "run_jarvis_health_check",
        "show_watchdog_status",
        "get_focused_app",
        "list_windows_detailed",
        "get_clipboard_summary",
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
        "discover_apps",
        "list_apps",
        "search_apps",
        "open_app",
        "approve_app",
        "forget_app",
        "list_websites",
        "open_website",
        "open_browser",
        "find_information_about",
        "open_best_result",
        "summarize_top_results",
        "compare_these_search_results",
        "extract_key_facts_from_this_page",
        "save_browser_research_report",
        "what_is_on_my_screen",
        "summarize_this_screen",
        "click_button_that_says",
        "type_this",
        "switch_to_chrome",
        "list_open_windows",
        "show_voice_health",
        "repair_memory_store",
        "show_browser_health",
        "show_desktop_operator_health",
        "show_system_health",
        "show_performance_report",
        "summarize_my_inbox",
        "show_urgent_emails",
        "summarize_my_calendar",
        "generate_product_readiness_report",
        "approve_website",
        "forget_website",
        "start_task",
        "show_task_plan",
        "approve_task_plan",
        "run_task_step",
        "stop_task",
        "show_task_status",
        "show_task_report",
        "show_task_findings",
        "propose_task_patch",
        "show_task_patch",
        "approve_task_patch",
        "reject_task_patch",
        "apply_task_patch",
        "rollback_task_patch",
        "show_last_diff",
        "review_trading_algorithm",
        "compare_backtest_to_paper",
        "find_live_backtest_mismatch",
        "generate_backtest_paper_report",
        "plan_experiments",
        "queue_task",
        "show_task_queue",
        "pause_task_queue",
        "resume_task_queue",
        "start_trading_workspace",
        "start_study_workspace",
        "start_dev_workspace",
        "suggest_ui_click",
        "confirm_ui_click",
        "browser_dom_read",
        "build_presentation",
        "create_report_document",
        "show_startup_health",
        "show_settings_status",
        "show_jarvis_status",
        "show_command_audit",
        "show_approvals",
        "approve_pending_action",
        "reject_pending_action",
        "clear_approvals",
        "show_overlay",
        "hide_overlay",
        "toggle_quiet_mode",
        "what_am_i_doing",
        "review_latest_patch",
        "summarize_recent_changes",
        "show_failing_tests",
        "summarize_this_file",
        "show_recent_commands",
        "explain_this_error",
        "start_study_mode",
        "focus_mode",
        "summarize_my_notes",
        "explain_this_code",
        "quiz_me",
        "what_should_i_study_next",
        "assistant_explain",
        "assistant_plan",
        "what_were_we_doing",
        "summarize_session",
        "switch_voice",
        "list_voices",
        "set_female_voice",
        "set_cinematic_voice",
        "set_voice_emotion",
        "benchmark_tts",
        "stop_speaking",
        "list_stt_engines",
        "show_stt_stack_status",
        "auto_tune_voice",
        "test_direct_speech",
        "verify_direct_speech_backend",
        "force_verified_direct_speech",
        "test_normal_speech",
        "audio_route_prove",
        "force_direct_pyttsx3_normal_mode",
        "test_subprocess_speech",
        "force_shell_tts_test",
        "voice_smoke_test",
        "foundation_health_check",
        "show_launcher_status",
        "show_runtime_threads",
        "show_control_status",
        "show_screen_status",
        "benchmark_voice_modes",
        "show_tts_threads",
    }
)

# Phase 40 — operating assistant (read-only awareness + rules assistant)
WORKSPACE_AWARENESS_ENABLED = os.getenv("WORKSPACE_AWARENESS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
WORKSPACE_SUGGESTIONS_ENABLED = os.getenv("WORKSPACE_SUGGESTIONS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
WORKSPACE_CONTEXT_PATH = DATA_DIR / "workspace_context.json"
ASSISTANT_MODE_ENABLED = os.getenv("ASSISTANT_MODE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SESSION_MEMORY_ENABLED = os.getenv("SESSION_MEMORY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SESSION_MEMORY_PATH = DATA_DIR / "session_memory.json"
SESSION_SUMMARY_EVERY_N = int(os.getenv("SESSION_SUMMARY_EVERY_N", "10"))
HUD_WORKSPACE_MODE_ENABLED = os.getenv("HUD_WORKSPACE_MODE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
HUD_SESSION_TIMELINE_ENABLED = os.getenv("HUD_SESSION_TIMELINE_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
# Phase 40b (later): LLM_ASSISTANT_ENABLED=false

# Vision / screen understanding (Phase 8 — read-only, local only)
VISION_ENABLED = os.getenv("VISION_ENABLED", "false").lower() in {"1", "true", "yes"}
VISION_CAPTURE_DIR = Path(
    os.getenv("VISION_CAPTURE_DIR", str(DATA_DIR / "screenshots"))
)
VISION_MAX_SCREENSHOT_AGE_SECONDS = int(
    os.getenv("VISION_MAX_SCREENSHOT_AGE_SECONDS", "300")
)
VISION_OCR_ENABLED = os.getenv("VISION_OCR_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
VISION_OCR_LANGUAGE = os.getenv("VISION_OCR_LANGUAGE", "eng+heb")
VISION_SAVE_SCREENSHOTS = os.getenv("VISION_SAVE_SCREENSHOTS", "false").lower() in {
    "1",
    "true",
    "yes",
}
VISION_REDACT_SENSITIVE_TEXT = os.getenv(
    "VISION_REDACT_SENSITIVE_TEXT", "true"
).lower() in {"1", "true", "yes"}
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
VISION_MAX_OCR_CHARS = int(os.getenv("VISION_MAX_OCR_CHARS", "3000"))
VISION_DISABLED_MESSAGE = (
    "Vision is disabled. Set VISION_ENABLED=true to enable read-only screen understanding."
)

# Screen understanding v1 (Phase 35 — read-only, no input control)
SCREEN_UNDERSTANDING_ENABLED = os.getenv(
    "SCREEN_UNDERSTANDING_ENABLED", "true"
).lower() in {"1", "true", "yes"}
SCREEN_CAPTURE_ALLOW = os.getenv("SCREEN_CAPTURE_ALLOW", "true").lower() in {
    "1",
    "true",
    "yes",
}
SCREEN_CAPTURE_MODE = os.getenv("SCREEN_CAPTURE_MODE", "active_window").strip().lower()
SCREEN_CAPTURE_SAVE_DEBUG = os.getenv("SCREEN_CAPTURE_SAVE_DEBUG", "false").lower() in {
    "1",
    "true",
    "yes",
}
SCREEN_CAPTURE_TEMP_DIR = Path(
    os.getenv("SCREEN_CAPTURE_TEMP_DIR", str(PROJECT_ROOT / "reports" / "screen_temp"))
)
SCREEN_OCR_ENABLED = os.getenv("SCREEN_OCR_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SCREEN_OCR_ENGINE = os.getenv("SCREEN_OCR_ENGINE", "auto").strip().lower()
SCREEN_MAX_TEXT_CHARS = int(os.getenv("SCREEN_MAX_TEXT_CHARS", "4000"))
SCREEN_REDACTION_ENABLED = os.getenv("SCREEN_REDACTION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SCREEN_BLOCK_SECRET_WINDOWS = os.getenv(
    "SCREEN_BLOCK_SECRET_WINDOWS", "true"
).lower() in {"1", "true", "yes"}
SCREEN_BLOCKED_WINDOW_KEYWORDS = os.getenv(
    "SCREEN_BLOCKED_WINDOW_KEYWORDS",
    ".env,secret,password,token,api key,private key,credential,wallet,recovery phrase,seed phrase",
)
SCREEN_FIND_MAX_RESULTS = int(os.getenv("SCREEN_FIND_MAX_RESULTS", "10"))
SCREEN_UNDERSTANDING_DISABLED_MESSAGE = (
    "Screen understanding is disabled. Set SCREEN_UNDERSTANDING_ENABLED=true "
    "to enable read-only screen awareness."
)

# Conversational layer v1 (Phase 37 — supervised, no auto-execute)
CONVERSATION_ENABLED = os.getenv("CONVERSATION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONVERSATION_CONTEXT_PATH = DATA_DIR / "conversation_context.json"
CONVERSATION_MAX_TURNS = int(os.getenv("CONVERSATION_MAX_TURNS", "10"))
CONVERSATION_MAX_SUMMARY_CHARS = int(os.getenv("CONVERSATION_MAX_SUMMARY_CHARS", "200"))
CONVERSATION_MAX_RAW_CHARS = int(os.getenv("CONVERSATION_MAX_RAW_CHARS", "120"))
CONVERSATION_CONTINUATION_ENABLED = os.getenv(
    "CONVERSATION_CONTINUATION_ENABLED", "true"
).lower() in {"1", "true", "yes"}
CONVERSATION_MAX_SUGGESTIONS = int(os.getenv("CONVERSATION_MAX_SUGGESTIONS", "4"))
CONVERSATION_FAST_ACK_ENABLED = os.getenv(
    "CONVERSATION_FAST_ACK_ENABLED", "true"
).lower() in {"1", "true", "yes"}
TTS_FAST_SUMMARY_ENABLED = os.getenv("TTS_FAST_SUMMARY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
TTS_READ_ONLY_COMPACT_SPEAK = os.getenv("TTS_READ_ONLY_COMPACT_SPEAK", "true").lower() in {
    "1",
    "true",
    "yes",
}
ASYNC_PERSISTENCE_ENABLED = os.getenv("ASYNC_PERSISTENCE_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}

# Runtime stability (Phase A1)
RUNTIME_MONITOR_ENABLED = os.getenv("RUNTIME_MONITOR_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
RUNTIME_MONITOR_INTERVAL_SECONDS = float(
    os.getenv("RUNTIME_MONITOR_INTERVAL_SECONDS", "30")
)
RUNTIME_EVENT_LOOP_LAG_WARN_SECONDS = float(
    os.getenv("RUNTIME_EVENT_LOOP_LAG_WARN_SECONDS", "5")
)
RUNTIME_DEADLOCK_SECONDS = float(os.getenv("RUNTIME_DEADLOCK_SECONDS", "90"))
RUNTIME_MEMORY_GROWTH_WARN_MB = float(os.getenv("RUNTIME_MEMORY_GROWTH_WARN_MB", "200"))
RUNTIME_MEMORY_GROWTH_WINDOW_SECONDS = float(
    os.getenv("RUNTIME_MEMORY_GROWTH_WINDOW_SECONDS", "300")
)
STT_TIMEOUT_SECONDS = float(os.getenv("STT_TIMEOUT_SECONDS", "45"))
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "20"))
TTS_SPEAK_MAX_SECONDS = float(os.getenv("TTS_SPEAK_MAX_SECONDS", "8"))
WATCHDOG_RECOVERY_ENABLED = os.getenv("WATCHDOG_RECOVERY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
WATCHDOG_MAX_RECOVERIES_PER_HOUR = int(
    os.getenv("WATCHDOG_MAX_RECOVERIES_PER_HOUR", "12")
)
OVERLAY_RECOVERY_BACKOFF_SECONDS = float(
    os.getenv("OVERLAY_RECOVERY_BACKOFF_SECONDS", "5")
)
RUNTIME_MONITOR_STATUS_PATH = DATA_DIR / "runtime_monitor_status.json"

# High-performance runtime (Phase A2)
EVENT_BUS_MAX_QUEUE_SIZE = int(os.getenv("EVENT_BUS_MAX_QUEUE_SIZE", "512"))
EVENT_BUS_BATCH_SIZE = int(os.getenv("EVENT_BUS_BATCH_SIZE", "16"))
EVENT_BUS_WORKER_COUNT = int(os.getenv("EVENT_BUS_WORKER_COUNT", "1"))
BACKGROUND_WORKER_COUNT = int(os.getenv("BACKGROUND_WORKER_COUNT", "2"))
BACKGROUND_WORK_QUEUE_SIZE = int(os.getenv("BACKGROUND_WORK_QUEUE_SIZE", "128"))
RUNTIME_CACHE_TTL_SECONDS = float(os.getenv("RUNTIME_CACHE_TTL_SECONDS", "30"))
RUNTIME_CACHE_MAX_ENTRIES = int(os.getenv("RUNTIME_CACHE_MAX_ENTRIES", "256"))
GPU_WORKLOAD_PREFER_GPU = os.getenv("GPU_WORKLOAD_PREFER_GPU", "true").lower() in {
    "1",
    "true",
    "yes",
}
GPU_WORKLOAD_BATCH_SIZE = int(os.getenv("GPU_WORKLOAD_BATCH_SIZE", "4"))
STREAM_PIPELINE_QUEUE_SIZE = int(os.getenv("STREAM_PIPELINE_QUEUE_SIZE", "64"))

# Observability (Phase A3)
OBSERVABILITY_ENABLED = os.getenv("OBSERVABILITY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
OBSERVABILITY_JSONL_PATH = DATA_DIR / "observability_events.jsonl"
OBSERVABILITY_TRACE_PATH = DATA_DIR / "runtime_traces.jsonl"
OBSERVABILITY_MAX_MEMORY_EVENTS = int(os.getenv("OBSERVABILITY_MAX_MEMORY_EVENTS", "500"))
OBSERVABILITY_LATENCY_BUCKETS_MS = tuple(
    int(v.strip())
    for v in os.getenv(
        "OBSERVABILITY_LATENCY_BUCKETS_MS",
        "25,50,100,250,500,1000,2500,5000,10000",
    ).split(",")
    if v.strip()
)
OVERLAY_FPS_SAMPLE_SECONDS = float(os.getenv("OVERLAY_FPS_SAMPLE_SECONDS", "5"))

# Computer control (Phase 12 — predefined UI actions only, disabled by default)
COMPUTER_CONTROL_ENABLED = os.getenv("COMPUTER_CONTROL_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
CLIPBOARD_MAX_CHARS = int(os.getenv("CLIPBOARD_MAX_CHARS", "1000"))
COMPUTER_CONTROL_DISABLED_MESSAGE = (
    "Computer control is disabled. Set COMPUTER_CONTROL_ENABLED=true to enable "
    "predefined window/clipboard actions (confirmation required for changes)."
)

# Desktop operator (Phase 63 — vision + control runtime)
DESKTOP_OPERATOR_ENABLED = os.getenv("DESKTOP_OPERATOR_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
# Alpha mode (Phase 68 — friend & family testing)
ALPHA_MODE = os.getenv("ALPHA_MODE", "false").lower() in {"1", "true", "yes"}
DEVELOPER_MODE = os.getenv("DEVELOPER_MODE", "false").lower() in {"1", "true", "yes"}
ALPHA_SUPPRESS_DEV_NOTIFICATIONS = os.getenv("ALPHA_SUPPRESS_DEV_NOTIFICATIONS", "true").lower() in {
    "1",
    "true",
    "yes",
}
ALPHA_FORCE_APPROVAL_GATES = os.getenv("ALPHA_FORCE_APPROVAL_GATES", "true").lower() in {"1", "true", "yes"}
ALPHA_SESSIONS_DIR = DATA_DIR / "alpha_sessions"

INTEGRATIONS_EMAIL_MODE = os.getenv("INTEGRATIONS_EMAIL_MODE", "mock").strip().lower()
INTEGRATIONS_CALENDAR_MODE = os.getenv("INTEGRATIONS_CALENDAR_MODE", "mock").strip().lower()
INTEGRATION_FIXTURES_DIR = DATA_DIR / "integration_fixtures"
REAL_VOICE_TEST_RECORD_SECONDS = float(os.getenv("REAL_VOICE_TEST_RECORD_SECONDS", "1.0"))
REAL_VOICE_VALIDATION_ENABLED = os.getenv("REAL_VOICE_VALIDATION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

DESKTOP_OPERATOR_SAFE_MODE = os.getenv("DESKTOP_OPERATOR_SAFE_MODE", "true").lower() in {
    "1",
    "true",
    "yes",
}

CONFIRMATION_REQUIRED_INTENTS: frozenset[str] = frozenset(
    {
        "shutdown_jarvis",
        "run_live_daily_loop",
        "run_live_weekly_loop",
        "stop_trading_loop",
        "enable_kill_switch",
        "disable_kill_switch",
        "enable_autostart",
        "disable_autostart",
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
        "apply_task_patch",
        "apply_approved_patch",
        "rollback_last_patch",
        "run_patch_workflow",
        "clear_stale_locks",
        "recover_overlay",
        "recover_voice_system",
        "restart_dashboard",
        "restart_wake_listener",
        "restart_operator_console",
        "restart_failed_worker",
        "confirm_ui_click",
        "click_button_that_says",
        "type_this",
        "switch_to_chrome",
    }
)

# Phase 21+ operating layer
PATCH_APPLY_ENABLED = os.getenv("PATCH_APPLY_ENABLED", "true").lower() in {"1", "true", "yes"}
TASK_QUEUE_MAX_RUNTIME_SECONDS = int(os.getenv("TASK_QUEUE_MAX_RUNTIME_SECONDS", "3600"))
BROWSER_DOM_ENABLED = os.getenv("BROWSER_DOM_ENABLED", "false").lower() in {"1", "true", "yes"}
BROWSER_DOM_ALLOWLIST = frozenset(
    s.strip().lower()
    for s in os.getenv(
        "BROWSER_DOM_ALLOWLIST",
        "dashboard,chatgpt,tradingview,yohananof",
    ).split(",")
    if s.strip()
)
GUIDED_UI_ENABLED = os.getenv("GUIDED_UI_ENABLED", "false").lower() in {"1", "true", "yes"}
ARTIFACTS_DIR = PROJECT_ROOT / "reports" / "artifacts"

# Legacy alias
PHASE1_INTENTS = IMPLEMENTED_INTENTS

# Voice / STT (Phase 2 — push-to-talk only)
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "false").lower() in {"1", "true", "yes"}
STT_ENGINE = os.getenv("STT_ENGINE", "faster_whisper")
_STT_MODEL_RAW = os.getenv("STT_MODEL", "medium").strip().lower()
STT_SAMPLE_RATE = int(os.getenv("STT_SAMPLE_RATE", "16000"))
STT_RECORDING_MAX_SECONDS = int(os.getenv("STT_RECORDING_MAX_SECONDS", "20"))
STT_DEVICE_REQUEST = (os.getenv("STT_DEVICE", "cuda") or "cuda").strip().lower()
STT_ACCELERATION_AUTO = os.getenv("STT_ACCELERATION_AUTO", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_FAST_PROFILE = os.getenv("STT_FAST_PROFILE", "false").lower() in {"1", "true", "yes"}
STT_PREFER_DIRECTML = os.getenv("STT_PREFER_DIRECTML", "false").lower() in {"1", "true", "yes"}
VOICE_PROFILE = os.getenv("VOICE_PROFILE", "balanced").strip().lower()
STT_ENABLE_NORMALIZATION = os.getenv("STT_ENABLE_NORMALIZATION", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_DEBUG_MIC = os.getenv("STT_DEBUG_MIC", "false").lower() in {"1", "true", "yes"}
STT_LOW_CONFIDENCE_LOGPROB = float(os.getenv("STT_LOW_CONFIDENCE_LOGPROB", "-0.8"))
STT_COMPUTE_TYPE = os.getenv("STT_COMPUTE_TYPE", "int8").strip()
STT_BEAM_SIZE = int(os.getenv("STT_BEAM_SIZE", "1"))
STT_VAD_FILTER = os.getenv("STT_VAD_FILTER", "true").lower() in {"1", "true", "yes"}
STT_MAX_RECORD_SECONDS = int(os.getenv("STT_MAX_RECORD_SECONDS", "5"))
STT_SILENCE_STOP_ENABLED = os.getenv("STT_SILENCE_STOP_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
STT_SILENCE_SECONDS = float(os.getenv("STT_SILENCE_SECONDS", "1.2"))
STT_LOW_CONFIDENCE_TTS_PROMPT = os.getenv("STT_LOW_CONFIDENCE_TTS_PROMPT", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_LOW_CONFIDENCE_BLOCK_WAKE = os.getenv("STT_LOW_CONFIDENCE_BLOCK_WAKE", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_SILENCE_THRESHOLD = float(os.getenv("STT_SILENCE_THRESHOLD", "0.012"))

# Fast voice mode — shorter capture, int8/small STT, silence stop (see .env.example)
FAST_VOICE_MODE = os.getenv("FAST_VOICE_MODE", "false").lower() in {"1", "true", "yes"}
VOICE_LATENCY_MODE = (os.getenv("VOICE_LATENCY_MODE", "") or "").strip().lower()
VOICE_LATENCY_INSTANT = VOICE_LATENCY_MODE == "instant"
VOICE_GRAMMAR_MIN_SCORE = int(os.getenv("VOICE_GRAMMAR_MIN_SCORE", "85"))

# Wake word (Phase 13 — activates temporary listening only, disabled by default)
WAKE_WORD_ENABLED = os.getenv("WAKE_WORD_ENABLED", "true").lower() in {"1", "true", "yes"}
WAKE_WORD_ENGINE = os.getenv("WAKE_WORD_ENGINE", "openwakeword")
WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "jarvis")
WAKE_WORD_MODEL_PATH = os.getenv("WAKE_WORD_MODEL_PATH", "").strip()
WAKE_WORD_DISPLAY_PHRASES = os.getenv(
    "WAKE_WORD_DISPLAY_PHRASES", "Jarvis, Hey Jarvis"
).strip()
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.6"))
WAKE_MAX_LISTEN_SECONDS = float(
    os.getenv(
        "WAKE_MAX_LISTEN_SECONDS",
        os.getenv("WAKE_WORD_LISTEN_SECONDS_AFTER_WAKE", "5"),
    )
)
WAKE_SILENCE_SECONDS = float(
    os.getenv("WAKE_SILENCE_SECONDS", os.getenv("STT_SILENCE_SECONDS", "1.6"))
)
WAKE_POST_SPEECH_BUFFER_MS = float(os.getenv("WAKE_POST_SPEECH_BUFFER_MS", "700"))
WAKE_MIN_SPEECH_SECONDS = float(os.getenv("WAKE_MIN_SPEECH_SECONDS", "0.45"))
WAKE_MIN_TOTAL_SECONDS = float(os.getenv("WAKE_MIN_TOTAL_SECONDS", "0.6"))
WAKE_COOLDOWN_SECONDS = float(
    os.getenv(
        "WAKE_COOLDOWN_SECONDS",
        os.getenv("WAKE_WORD_COOLDOWN_SECONDS", "4"),
    )
)
WAKE_EARLY_STOP_ENABLED = os.getenv("WAKE_EARLY_STOP_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
WAKE_WORD_LISTEN_SECONDS_AFTER_WAKE = WAKE_MAX_LISTEN_SECONDS
WAKE_WORD_COOLDOWN_SECONDS = WAKE_COOLDOWN_SECONDS
WAKE_WORD_SAMPLE_RATE = int(os.getenv("WAKE_WORD_SAMPLE_RATE", "16000"))

from voice.stt_config import normalize_stt_model, resolve_stt_language  # noqa: E402
from voice.stt_profile import apply_voice_profile  # noqa: E402

_stt_profile = apply_voice_profile(
    voice_profile=VOICE_PROFILE,
    stt_fast_profile=STT_FAST_PROFILE,
    fast_voice_mode=FAST_VOICE_MODE,
    model_raw=_STT_MODEL_RAW,
    beam_size=STT_BEAM_SIZE,
    wake_max_listen_seconds=WAKE_MAX_LISTEN_SECONDS,
    low_confidence_block_wake_env=STT_LOW_CONFIDENCE_BLOCK_WAKE,
)
if _stt_profile.applied:
    _STT_MODEL_RAW = _stt_profile.model
    STT_BEAM_SIZE = _stt_profile.beam_size
    WAKE_MAX_LISTEN_SECONDS = _stt_profile.wake_max_listen_seconds
    WAKE_WORD_LISTEN_SECONDS_AFTER_WAKE = WAKE_MAX_LISTEN_SECONDS
    FAST_VOICE_MODE = _stt_profile.fast_voice_mode
    if _stt_profile.low_confidence_block_wake is not None:
        STT_LOW_CONFIDENCE_BLOCK_WAKE = _stt_profile.low_confidence_block_wake

if VOICE_LATENCY_INSTANT:
    _instant_model = normalize_stt_model(_STT_MODEL_RAW or "base")
    if _instant_model not in {"base", "tiny"}:
        _instant_model = "base"
    _STT_MODEL_RAW = _instant_model
    STT_BEAM_SIZE = 1
    STT_FAST_PROFILE = True
    FAST_VOICE_MODE = True

STT_MODEL = normalize_stt_model(_STT_MODEL_RAW)
STT_LANGUAGE = resolve_stt_language(os.getenv("STT_LANGUAGE"))
# Validated: en (default) or he only when STT_LANGUAGE=he explicitly
assert STT_LANGUAGE in {"en", "he"}

# Legacy alias: explicit cuda/cpu only; auto resolved via stt_acceleration
STT_DEVICE = STT_DEVICE_REQUEST if STT_DEVICE_REQUEST in {"cuda", "cpu"} else ""

from voice.stt_acceleration import configure_stt_runtime  # noqa: E402

STT_RUNTIME = configure_stt_runtime(
    device_request=STT_DEVICE_REQUEST,
    acceleration_auto=STT_ACCELERATION_AUTO,
    fast_profile=STT_FAST_PROFILE or VOICE_PROFILE == "fast",
    compute_type_override=STT_COMPUTE_TYPE,
    prefer_directml=STT_PREFER_DIRECTML,
)
STT_RESOLVED_DEVICE = STT_RUNTIME.whisper_device
STT_RESOLVED_COMPUTE_TYPE = STT_RUNTIME.compute_type
WAKE_WORD_NOTIFY = os.getenv("WAKE_WORD_NOTIFY", "true").lower() in {"1", "true", "yes"}
WAKE_WORD_DEBUG = os.getenv("WAKE_WORD_DEBUG", "false").lower() in {"1", "true", "yes"}

# Background quiet mode (tray/wake — HUD hidden until wake or explicit command)
BACKGROUND_MODE = os.getenv("BACKGROUND_MODE", "false").lower() in {"1", "true", "yes"}
START_MINIMIZED = os.getenv("START_MINIMIZED", "false").lower() in {"1", "true", "yes"}
OVERLAY_START_HIDDEN = os.getenv("OVERLAY_START_HIDDEN", "false").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_ON_WAKE = os.getenv("OVERLAY_SHOW_ON_WAKE", "true").lower() in {
    "1",
    "true",
    "yes",
}

# Visual overlay (Phase 14 — UI only, wake/voice feedback)
OVERLAY_ENABLED = os.getenv("OVERLAY_ENABLED", "false").lower() in {"1", "true", "yes"}
# Set JARVIS_OVERLAY_QT=0 to run overlay state/hooks without a real QApplication (pytest default).
OVERLAY_QT_ENABLED = os.getenv("JARVIS_OVERLAY_QT", "1").lower() in {"1", "true", "yes"}
OVERLAY_AUTO_HIDE_SECONDS = float(os.getenv("OVERLAY_AUTO_HIDE_SECONDS", "12"))
OVERLAY_STAY_OPEN_ON_ERROR = os.getenv("OVERLAY_STAY_OPEN_ON_ERROR", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_STAY_OPEN_ON_SUGGESTIONS = os.getenv(
    "OVERLAY_STAY_OPEN_ON_SUGGESTIONS", "true"
).lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_READY_VISIBLE_SECONDS = float(os.getenv("OVERLAY_READY_VISIBLE_SECONDS", "8"))
OVERLAY_ALWAYS_ON_TOP = os.getenv("OVERLAY_ALWAYS_ON_TOP", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_OPACITY = float(os.getenv("OVERLAY_OPACITY", "0.88"))
OVERLAY_SHOW_TRANSCRIPT = os.getenv("OVERLAY_SHOW_TRANSCRIPT", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_RESULT = os.getenv("OVERLAY_SHOW_RESULT", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_THEME = os.getenv("OVERLAY_THEME", "jarvis_blue").strip().lower()
OVERLAY_STYLE = os.getenv("OVERLAY_STYLE", "premium_ironman_full").strip().lower()
OVERLAY_WIDTH_RATIO = float(os.getenv("OVERLAY_WIDTH_RATIO", "0.92"))
OVERLAY_HEIGHT_RATIO = float(os.getenv("OVERLAY_HEIGHT_RATIO", "0.88"))
OVERLAY_POSITION = os.getenv("OVERLAY_POSITION", "center").strip().lower()
OVERLAY_SHOW_SYSTEM_PANELS = os.getenv("OVERLAY_SHOW_SYSTEM_PANELS", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_COMMAND_HISTORY = os.getenv("OVERLAY_SHOW_COMMAND_HISTORY", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_WAVEFORM = os.getenv("OVERLAY_SHOW_WAVEFORM", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_HUD_LABELS = os.getenv("OVERLAY_SHOW_HUD_LABELS", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_AUDIO_PULSE = os.getenv("OVERLAY_SHOW_AUDIO_PULSE", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_SHOW_ROTATING_RINGS = os.getenv("OVERLAY_SHOW_ROTATING_RINGS", "true").lower() in {
    "1",
    "true",
    "yes",
}
OVERLAY_FADE_MS = int(os.getenv("OVERLAY_FADE_MS", "250"))
OVERLAY_MAX_TEXT_CHARS = int(os.getenv("OVERLAY_MAX_TEXT_CHARS", "500"))
OVERLAY_TEST_DISPLAY_SECONDS = float(os.getenv("OVERLAY_TEST_DISPLAY_SECONDS", "5"))

# Wake greeting (TTS only after wake word)
JARVIS_USER_NAME = os.getenv("JARVIS_USER_NAME", "Yoav").strip()
WAKE_GREETING_ENABLED = os.getenv("WAKE_GREETING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
WAKE_GREETING_TEXT = os.getenv("WAKE_GREETING_TEXT", "Hey {name}")
WAKE_GREETING_ASYNC = os.getenv("WAKE_GREETING_ASYNC", "true").lower() in {
    "1",
    "true",
    "yes",
}
WAKE_GREETING_MAX_DELAY_SECONDS = float(os.getenv("WAKE_GREETING_MAX_DELAY_SECONDS", "0.2"))

# TTS (Phase 3 / 18 — edge-tts premium + pyttsx3 fallback)
TTS_ENABLED = os.getenv("TTS_ENABLED", "false").lower() in {"1", "true", "yes"}
TTS_ENGINE = os.getenv("TTS_ENGINE", "pyttsx3").strip().lower()
TTS_FORCE_ENGINE = os.getenv("TTS_FORCE_ENGINE", "").strip().lower()
TTS_BACKEND = os.getenv("TTS_BACKEND", "").strip().lower()
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "he")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-GuyNeural").strip()
TTS_RATE_RAW = os.getenv("TTS_RATE", "+0%").strip()
TTS_VOLUME = float(os.getenv("TTS_VOLUME", "1.0"))
TTS_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "500"))
TTS_ASYNC = os.getenv("TTS_ASYNC", "false").lower() in {"1", "true", "yes"}
TTS_FORCE_DEFAULT_WINDOWS_DEVICE = os.getenv(
    "TTS_FORCE_DEFAULT_WINDOWS_DEVICE", "false"
).lower() in {"1", "true", "yes"}
TTS_FORCE_WINDOWS_DEFAULT_OUTPUT = os.getenv(
    "TTS_FORCE_WINDOWS_DEFAULT_OUTPUT",
    os.getenv("TTS_FORCE_DEFAULT_WINDOWS_DEVICE", "false"),
).lower() in {"1", "true", "yes"}
TTS_WARN_INACTIVE_DEVICE = os.getenv("TTS_WARN_INACTIVE_DEVICE", "true").lower() in {
    "1",
    "true",
    "yes",
}
TTS_STARTUP_SELF_TEST = os.getenv("TTS_STARTUP_SELF_TEST", "true").lower() in {
    "1",
    "true",
    "yes",
}

# Phase 42 — world-class speech recognition stack
STT_STACK_ENABLED = os.getenv("STT_STACK_ENABLED", "false").lower() in {"1", "true", "yes"}
STT_ENGINE_CHAIN = os.getenv(
    "STT_ENGINE_CHAIN",
    "faster_whisper,onnx_whisper,whisper_cpp,parakeet,deepgram_local",
).strip()
STT_FUSION_ENABLED = os.getenv("STT_FUSION_ENABLED", "true").lower() in {"1", "true", "yes"}
STT_PARTIAL_STREAMING_ENABLED = os.getenv("STT_PARTIAL_STREAMING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_INTENT_CORRECTION_ENABLED = os.getenv("STT_INTENT_CORRECTION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_TRANSCRIPT_REPAIR_ENABLED = os.getenv("STT_TRANSCRIPT_REPAIR_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_VOICE_FINGERPRINT_ENABLED = os.getenv("STT_VOICE_FINGERPRINT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_NOISE_SUPPRESSION_ENABLED = os.getenv("STT_NOISE_SUPPRESSION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_ECHO_CANCELLATION_ENABLED = os.getenv("STT_ECHO_CANCELLATION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_AUTO_LANGUAGE_DETECT = os.getenv("STT_AUTO_LANGUAGE_DETECT", "false").lower() in {
    "1",
    "true",
    "yes",
}
STT_RETRY_MAX_ATTEMPTS = int(os.getenv("STT_RETRY_MAX_ATTEMPTS", "2"))
STT_STACK_PATH = DATA_DIR / "stt_stack.json"
WHISPER_CPP_BINARY = os.getenv("WHISPER_CPP_BINARY", "").strip()
WHISPER_CPP_MODEL = os.getenv("WHISPER_CPP_MODEL", "").strip()
PARAKEET_MODEL_PATH = os.getenv("PARAKEET_MODEL_PATH", "").strip()
DEEPGRAM_LOCAL_URL = os.getenv("DEEPGRAM_LOCAL_URL", "").strip()

# Phase 42 v2 — elite speech recognition (multipass + grammar + calibration)
STT_MULTIPASS_ENABLED = os.getenv("STT_MULTIPASS_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
STT_RETRY_ON_UNKNOWN = os.getenv("STT_RETRY_ON_UNKNOWN", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_ACCURATE_RETRY_BEAM_SIZE = int(os.getenv("STT_ACCURATE_RETRY_BEAM_SIZE", "5"))
STT_ACCURATE_RETRY_MAX_MS = float(os.getenv("STT_ACCURATE_RETRY_MAX_MS", "2500"))
VOICE_CALIBRATION_ENABLED = os.getenv("VOICE_CALIBRATION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
VOICE_CALIBRATION_MAX_SAMPLES = int(os.getenv("VOICE_CALIBRATION_MAX_SAMPLES", "20"))
WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS = float(
    os.getenv("WAKE_FALSE_TRIGGER_COOLDOWN_SECONDS", "2.5")
)

# Phase 42.5 — semantic language understanding (local, router executes)
SEMANTIC_UNDERSTANDING_ENABLED = os.getenv("SEMANTIC_UNDERSTANDING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SEMANTIC_LLM_ENABLED = os.getenv("SEMANTIC_LLM_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
SEMANTIC_LLM_PROVIDER = os.getenv("SEMANTIC_LLM_PROVIDER", "ollama").strip().lower()
SEMANTIC_LLM_MODEL = os.getenv("SEMANTIC_LLM_MODEL", "llama3.1:8b").strip()
SEMANTIC_LLM_TIMEOUT_SECONDS = int(os.getenv("SEMANTIC_LLM_TIMEOUT_SECONDS", "4"))
SEMANTIC_MIN_CONFIDENCE = float(os.getenv("SEMANTIC_MIN_CONFIDENCE", "0.72"))
VOCABULARY_CORRECTION_ENABLED = os.getenv("VOCABULARY_CORRECTION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
VOCABULARY_MAX_EDIT_DISTANCE = int(os.getenv("VOCABULARY_MAX_EDIT_DISTANCE", "2"))

# Phase 42.6 — rolling-buffer streaming STT
STT_STREAMING_BUFFER_ENABLED = os.getenv("STT_STREAMING_BUFFER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_STREAM_MAX_BUFFER_SECONDS = min(
    3.0,
    max(1.5, float(os.getenv("STT_STREAM_MAX_BUFFER_SECONDS", "2.5"))),
)
STT_ROLLING_BUFFER_SECONDS = min(
    3.0,
    max(
        1.5,
        float(os.getenv("STT_ROLLING_BUFFER_SECONDS", str(STT_STREAM_MAX_BUFFER_SECONDS))),
    ),
)
STT_PARTIAL_INTERVAL_MS = min(
    500.0,
    max(250.0, float(os.getenv("STT_PARTIAL_INTERVAL_MS", "250"))),
)
STT_STREAM_CHUNK_MS = float(os.getenv("STT_STREAM_CHUNK_MS", "100"))
STT_STREAM_OVERLAP_MS = float(os.getenv("STT_STREAM_OVERLAP_MS", "50"))
STT_STREAM_ENDPOINT_SILENCE_MS = float(os.getenv("STT_STREAM_ENDPOINT_SILENCE_MS", "700"))
STT_STREAM_MIN_SPEECH_MS = float(os.getenv("STT_STREAM_MIN_SPEECH_MS", "250"))
STT_STREAM_MIN_PARTIAL_CONTEXT_MS = max(
    250.0,
    float(os.getenv("STT_STREAM_MIN_PARTIAL_CONTEXT_MS", "250")),
)
STT_INCREMENTAL_DECODE_MIN_MS = float(os.getenv("STT_INCREMENTAL_DECODE_MIN_MS", "250"))
STT_INTENT_PREFETCH_ENABLED = os.getenv("STT_INTENT_PREFETCH_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
STT_STREAM_GPU_FIRST = os.getenv("STT_STREAM_GPU_FIRST", "true").lower() in {"1", "true", "yes"}
STT_STREAM_DECODE_MAX_MS = float(os.getenv("STT_STREAM_DECODE_MAX_MS", "1200"))
STT_STREAM_PARTIAL_DECODE_MAX_MS = float(os.getenv("STT_STREAM_PARTIAL_DECODE_MAX_MS", "2500"))
STT_STREAM_PARTIAL_TIMEOUT_SECONDS = float(
    os.getenv("STT_STREAM_PARTIAL_TIMEOUT_SECONDS", "2.5")
)
STT_STREAM_STARTUP_GRACE_SECONDS = float(
    os.getenv("STT_STREAM_STARTUP_GRACE_SECONDS", "10.0")
)
STT_STREAM_PARTIAL_MAX_FAILURES = max(
    1, int(os.getenv("STT_STREAM_PARTIAL_MAX_FAILURES", "3"))
)
STT_STREAM_PARTIAL_RETRY_COUNT = max(
    0, int(os.getenv("STT_STREAM_PARTIAL_RETRY_COUNT", "2"))
)
STT_STREAM_TEST_SECONDS = float(os.getenv("STT_STREAM_TEST_SECONDS", "8.0"))


def stt_stream_partial_timeout_ms() -> float:
    """Partial decode watchdog budget (ms). Prefers STT_STREAM_PARTIAL_TIMEOUT_SECONDS."""
    if os.getenv("STT_STREAM_PARTIAL_TIMEOUT_SECONDS"):
        return max(500.0, STT_STREAM_PARTIAL_TIMEOUT_SECONDS * 1000.0)
    return max(500.0, float(STT_STREAM_PARTIAL_DECODE_MAX_MS))
STT_STREAM_PARTIAL_ACCURATE_RETRY_ENABLED = os.getenv(
    "STT_STREAM_PARTIAL_ACCURATE_RETRY_ENABLED", "false"
).lower() in {"1", "true", "yes"}
STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED = os.getenv(
    "STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED", "true"
).lower() in {"1", "true", "yes"}
STT_WAKE_FALLBACK_TIMEOUT_SECONDS = float(os.getenv("STT_WAKE_FALLBACK_TIMEOUT_SECONDS", "12"))


def streaming_chunk_samples(*, sample_rate: int | None = None) -> int:
    """Mic chunk size from STT_STREAM_CHUNK_MS (default 100ms at 16 kHz)."""
    rate = sample_rate or STT_SAMPLE_RATE
    return max(320, int(rate * (STT_STREAM_CHUNK_MS / 1000.0)))


# Phase 42.7 — semantic streaming conversation engine
CONVERSATION_SEMANTIC_STREAM_ENABLED = os.getenv(
    "CONVERSATION_SEMANTIC_STREAM_ENABLED", "true"
).lower() in {"1", "true", "yes"}
CONV_SEMANTIC_UPDATE_MIN_MS = float(os.getenv("CONV_SEMANTIC_UPDATE_MIN_MS", "80"))
CONV_SEMANTIC_LATENCY_BUDGET_MS = float(os.getenv("CONV_SEMANTIC_LATENCY_BUDGET_MS", "200"))
CONV_ACTION_PLAN_ENABLED = os.getenv("CONV_ACTION_PLAN_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_MULTI_INTENT_ENABLED = os.getenv("CONV_MULTI_INTENT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_CORRECTION_ENABLED = os.getenv("CONV_CORRECTION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_CONTEXT_CARRY_ENABLED = os.getenv("CONV_CONTEXT_CARRY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_INTERRUPTION_ENABLED = os.getenv("CONV_INTERRUPTION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_REFORMULATION_ENABLED = os.getenv("CONV_REFORMULATION_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
CONV_CONFIDENCE_STABILITY_THRESHOLD = float(
    os.getenv("CONV_CONFIDENCE_STABILITY_THRESHOLD", "0.72")
)
CONV_TURN_PAUSE_MS = float(os.getenv("CONV_TURN_PAUSE_MS", "400"))

if VOICE_LATENCY_INSTANT:
    STT_MULTIPASS_ENABLED = False
    STT_STACK_ENABLED = False
    STT_RETRY_ON_UNKNOWN = False
    STT_STREAMING_BUFFER_ENABLED = True
    CONVERSATION_SEMANTIC_STREAM_ENABLED = True
    STT_STREAM_PARTIAL_ACCURATE_RETRY_ENABLED = False
    STT_STREAM_FINAL_ACCURATE_RETRY_ENABLED = False
    STT_STREAM_MAX_BUFFER_SECONDS = min(
        2.5,
        max(1.5, float(os.getenv("STT_STREAM_MAX_BUFFER_SECONDS", "2.0"))),
    )
    STT_ROLLING_BUFFER_SECONDS = min(
        2.5,
        max(
            1.5,
            float(os.getenv("STT_ROLLING_BUFFER_SECONDS", str(STT_STREAM_MAX_BUFFER_SECONDS))),
        ),
    )
    STT_PARTIAL_INTERVAL_MS = min(
        250.0,
        max(150.0, float(os.getenv("STT_PARTIAL_INTERVAL_MS", "200"))),
    )
    STT_STREAM_MIN_PARTIAL_CONTEXT_MS = min(
        250.0,
        max(150.0, float(os.getenv("STT_STREAM_MIN_PARTIAL_CONTEXT_MS", "200"))),
    )
    STT_INCREMENTAL_DECODE_MIN_MS = min(
        STT_PARTIAL_INTERVAL_MS,
        float(os.getenv("STT_INCREMENTAL_DECODE_MIN_MS", str(STT_PARTIAL_INTERVAL_MS))),
    )
    STT_STREAM_ENDPOINT_SILENCE_MS = min(
        500.0,
        max(350.0, float(os.getenv("STT_STREAM_ENDPOINT_SILENCE_MS", "450"))),
    )

# Phase 41.6 — stable TTS playback (pyttsx3 direct, blocking)
TTS_SAFE_MODE = os.getenv("TTS_SAFE_MODE", "false").lower() in {"1", "true", "yes"}
COMPLETION_GRACE_RECOVERY_ENABLED = os.getenv(
    "COMPLETION_GRACE_RECOVERY_ENABLED", "true"
).lower() in {"1", "true", "yes"}
FORCE_AUDIO_SUCCESS_FOR_DEBUG = os.getenv("FORCE_AUDIO_SUCCESS_FOR_DEBUG", "false").lower() in {
    "1",
    "true",
    "yes",
}
TTS_DEBUG_PLAYBACK = os.getenv("TTS_DEBUG_PLAYBACK", "false").lower() in {
    "1",
    "true",
    "yes",
}

# Phase 41 — premium human voice stack
TTS_STREAMING_ENABLED = os.getenv("TTS_STREAMING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
TTS_BARGE_IN_ENABLED = os.getenv("TTS_BARGE_IN_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

# Phase 57 — realtime streaming TTS (pyttsx3 fallback-only in normal path)
REALTIME_TTS_ENABLED = os.getenv("REALTIME_TTS_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
PYTTSX3_FALLBACK_ONLY = os.getenv("PYTTSX3_FALLBACK_ONLY", "true").lower() in {
    "1",
    "true",
    "yes",
}
REALTIME_TTS_PROVIDER_ORDER = os.getenv(
    "REALTIME_TTS_PROVIDER_ORDER",
    "openai_realtime,elevenlabs,piper,pyttsx3_fallback",
).strip()
REALTIME_TTS_PREFERRED = os.getenv("REALTIME_TTS_PREFERRED", "").strip()
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy").strip()
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5").strip()
REALTIME_TTS_EMOTION = os.getenv("REALTIME_TTS_EMOTION", "neutral").strip()
REALTIME_STREAM_MIN_PLAY_BYTES = int(os.getenv("REALTIME_STREAM_MIN_PLAY_BYTES", "4096"))
REALTIME_STREAM_FIRST_PLAY_MAX_MS = float(os.getenv("REALTIME_STREAM_FIRST_PLAY_MAX_MS", "120"))
REALTIME_STREAM_ADAPTIVE_BUFFER = os.getenv("REALTIME_STREAM_ADAPTIVE_BUFFER", "true").lower() in {
    "1",
    "true",
    "yes",
}
ELEVENLABS_WEBSOCKET_ENABLED = os.getenv("ELEVENLABS_WEBSOCKET_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
ELEVENLABS_WS_KEEPALIVE_SECONDS = float(os.getenv("ELEVENLABS_WS_KEEPALIVE_SECONDS", "20"))
REALTIME_FULL_DUPLEX_ENABLED = os.getenv("REALTIME_FULL_DUPLEX_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
REALTIME_ULTRA_LOW_LATENCY = os.getenv("REALTIME_ULTRA_LOW_LATENCY", "true").lower() in {
    "1",
    "true",
    "yes",
}
# Phase 59 — human conversational runtime
HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = os.getenv(
    "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", "true"
).lower() in {"1", "true", "yes"}
CONVERSATION_CONTINUOUS_MIC_ENABLED = os.getenv(
    "CONVERSATION_CONTINUOUS_MIC_ENABLED", "true"
).lower() in {"1", "true", "yes"}
CONVERSATION_PARTIAL_INTERVAL_MS = float(os.getenv("CONVERSATION_PARTIAL_INTERVAL_MS", "150"))
CONVERSATION_TURN_MAX_SECONDS = float(os.getenv("CONVERSATION_TURN_MAX_SECONDS", "45"))
CONVERSATION_SESSION_MAX_SECONDS = float(os.getenv("CONVERSATION_SESSION_MAX_SECONDS", "600"))
CONVERSATION_SESSION_IDLE_SECONDS = float(os.getenv("CONVERSATION_SESSION_IDLE_SECONDS", "60"))
CONVERSATION_IDLE_PROACTIVE_ENABLED = os.getenv(
    "CONVERSATION_IDLE_PROACTIVE_ENABLED", "true"
).lower() in {"1", "true", "yes"}
CONVERSATION_IDLE_PROACTIVE_SECONDS = float(os.getenv("CONVERSATION_IDLE_PROACTIVE_SECONDS", "120"))
CONVERSATION_TARGET_FIRST_PARTIAL_STT_MS = float(
    os.getenv("CONVERSATION_TARGET_FIRST_PARTIAL_STT_MS", "150")
)
CONVERSATION_TARGET_LLM_FIRST_TOKEN_MS = float(
    os.getenv("CONVERSATION_TARGET_LLM_FIRST_TOKEN_MS", "250")
)
CONVERSATION_TARGET_TTS_FIRST_AUDIO_MS = float(
    os.getenv("CONVERSATION_TARGET_TTS_FIRST_AUDIO_MS", "250")
)
CONVERSATION_TARGET_INTERRUPT_PAUSE_MS = float(
    os.getenv("CONVERSATION_TARGET_INTERRUPT_PAUSE_MS", "100")
)
CONVERSATION_TARGET_PERCEIVED_DELAY_MS = float(
    os.getenv("CONVERSATION_TARGET_PERCEIVED_DELAY_MS", "400")
)
TTS_POLICY_TRACE = os.getenv("TTS_POLICY_TRACE", "true").lower() in {"1", "true", "yes"}
TTS_PRIMARY_BACKEND = os.getenv("TTS_PRIMARY_BACKEND", "realtime").strip().lower()
TTS_FALLBACK_BACKEND = os.getenv("TTS_FALLBACK_BACKEND", "pyttsx3_direct").strip().lower()
VOICE_COMMAND_GUARD_ENABLED = os.getenv("VOICE_COMMAND_GUARD_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
VOICE_GUARD_MIN_WORDS = int(os.getenv("VOICE_GUARD_MIN_WORDS", "3"))
VOICE_GUARD_MIN_CONFIDENCE = float(os.getenv("VOICE_GUARD_MIN_CONFIDENCE", str(CONFIDENCE_THRESHOLD)))
VOICE_RISKY_INTENTS: frozenset[str] = frozenset(
    s.strip()
    for s in os.getenv(
        "VOICE_RISKY_INTENTS",
        "open_website,open_app,delete_file,forget_memory,apply_task_patch,apply_approved_patch,"
        "run_patch_workflow,run_workflow,send_email,execute_shell,run_live_daily_loop,"
        "run_live_weekly_loop,stop_trading_loop,enable_kill_switch,disable_kill_switch,"
        "focus_window,copy_text_to_clipboard,clear_clipboard,write_file,apply_engineering_patch",
    ).split(",")
    if s.strip()
)
VOICE_CONFIRMATION_INTENTS: frozenset[str] = frozenset(
    s.strip()
    for s in os.getenv(
        "VOICE_CONFIRMATION_INTENTS",
        "open_website,open_app,delete_file,apply_task_patch,apply_approved_patch,"
        "run_patch_workflow,run_workflow,send_email,execute_shell,run_live_daily_loop,"
        "run_live_weekly_loop,stop_trading_loop,enable_kill_switch,disable_kill_switch",
    ).split(",")
    if s.strip()
)
VOICE_STACK_PATH = DATA_DIR / "voice_stack.json"
AUDIO_ROUTING_PATH = DATA_DIR / "audio_routing.json"
PIPER_BIN = os.getenv("PIPER_BIN", "piper").strip()
PIPER_MODEL = os.getenv("PIPER_MODEL", "").strip()
XTTS_MODEL_PATH = os.getenv("XTTS_MODEL_PATH", "").strip()
STYLETTS2_SCRIPT = os.getenv("STYLETTS2_SCRIPT", "").strip()
VOICE_STACK_STARTUP_CALIBRATION = os.getenv(
    "VOICE_STACK_STARTUP_CALIBRATION", "true"
).lower() in {"1", "true", "yes"}

from voice.tts_config import resolve_pyttsx_rate  # noqa: E402

TTS_RATE = resolve_pyttsx_rate(TTS_RATE_RAW)

# Overlay update queue (drop stale UI updates when full)
OVERLAY_UPDATE_QUEUE_SIZE = int(os.getenv("OVERLAY_UPDATE_QUEUE_SIZE", "32"))
OVERLAY_STARTUP_WAIT_SECONDS = float(os.getenv("OVERLAY_STARTUP_WAIT_SECONDS", "0.5"))

# LLM intent classifier (Phase 4 — classification only, no execution)
LLM_CLASSIFIER_ENABLED = os.getenv("LLM_CLASSIFIER_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "8"))
LLM_MIN_CONFIDENCE = float(os.getenv("LLM_MIN_CONFIDENCE", "0.75"))
LLM_FALLBACK_TO_RULES = os.getenv("LLM_FALLBACK_TO_RULES", "true").lower() in {
    "1",
    "true",
    "yes",
}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

# Voice runtime preset (stable = CPU small-model baseline; overrides conflicting keys)
VOICE_RUNTIME_MODE = (os.getenv("VOICE_RUNTIME_MODE", "") or "").strip().lower()
VOICE_RUNTIME_STABLE = VOICE_RUNTIME_MODE == "stable"

from voice.runtime_mode import apply_voice_runtime_mode  # noqa: E402

apply_voice_runtime_mode()

from core.env_precedence import validate_realtime_experimental_resolution  # noqa: E402

validate_realtime_experimental_resolution()
