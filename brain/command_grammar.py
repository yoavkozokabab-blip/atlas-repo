"""Deterministic command grammar engine (Phase 42 v2) — classification aid only."""

from __future__ import annotations

from dataclasses import dataclass

from config import VOICE_GRAMMAR_MIN_SCORE
from core.types import CommandRequest, Intent

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore[assignment]


@dataclass(frozen=True)
class GrammarMatchResult:
    """Structured grammar scoring output (no execution)."""

    best_command: str
    intent: Intent
    confidence: float
    matched_phrase: str
    correction_reason: str
    corrected_text: str
    fuzzy_score: int


@dataclass(frozen=True)
class _GrammarEntry:
    phrase: str
    intent: Intent
    confidence: float
    params: dict | None = None


# Canonical phrases for supported voice commands (longest match wins).
_COMMAND_GRAMMAR: list[_GrammarEntry] = [
    _GrammarEntry("foundation health check", Intent.FOUNDATION_HEALTH_CHECK, 0.97),
    _GrammarEntry("show launcher status", Intent.SHOW_LAUNCHER_STATUS, 0.96),
    _GrammarEntry("show runtime threads", Intent.SHOW_RUNTIME_THREADS, 0.96),
    _GrammarEntry("show control status", Intent.SHOW_CONTROL_STATUS, 0.96),
    _GrammarEntry("show screen status", Intent.SHOW_SCREEN_STATUS, 0.96),
    _GrammarEntry("phase 45 status", Intent.PHASE45_STATUS, 0.97),
    _GrammarEntry("phase 46 status", Intent.PHASE46_STATUS, 0.97),
    _GrammarEntry("inspect project", Intent.INSPECT_PROJECT, 0.97),
    _GrammarEntry("inspect website project", Intent.INSPECT_WEBSITE_PROJECT, 0.97),
    _GrammarEntry("summarize current project", Intent.SUMMARIZE_CURRENT_PROJECT, 0.97),
    _GrammarEntry("find failing tests", Intent.FIND_FAILING_TESTS, 0.97),
    _GrammarEntry("explain latest error", Intent.EXPLAIN_LATEST_ERROR, 0.97),
    _GrammarEntry("investigate trading mismatch", Intent.INVESTIGATE_TRADING_MISMATCH, 0.97),
    _GrammarEntry("compare live vs backtest", Intent.COMPARE_LIVE_VS_BACKTEST, 0.97),
    _GrammarEntry("inspect latest live report", Intent.INSPECT_LATEST_LIVE_REPORT, 0.97),
    _GrammarEntry("inspect latest backtest report", Intent.INSPECT_LATEST_BACKTEST_REPORT, 0.97),
    _GrammarEntry("find recent code changes", Intent.FIND_RECENT_CODE_CHANGES, 0.97),
    _GrammarEntry("propose investigation plan", Intent.PROPOSE_INVESTIGATION_PLAN, 0.97),
    _GrammarEntry("run safe diagnostics", Intent.RUN_SAFE_DIAGNOSTICS, 0.97),
    _GrammarEntry("generate findings report", Intent.GENERATE_FINDINGS_REPORT, 0.97),
    _GrammarEntry("build investigation graph", Intent.BUILD_INVESTIGATION_GRAPH, 0.97),
    _GrammarEntry("show investigation graph", Intent.SHOW_INVESTIGATION_GRAPH, 0.97),
    _GrammarEntry("search investigation graph", Intent.SEARCH_INVESTIGATION_GRAPH, 0.93),
    _GrammarEntry("trace algorithm behavior", Intent.TRACE_ALGORITHM_BEHAVIOR, 0.97),
    _GrammarEntry("diff live and backtest logic", Intent.DIFF_LIVE_BACKTEST_LOGIC, 0.97),
    _GrammarEntry("hunt algorithm bugs", Intent.HUNT_ALGORITHM_BUGS, 0.97),
    _GrammarEntry("propose algorithm patch", Intent.PROPOSE_ALGORITHM_PATCH, 0.97),
    _GrammarEntry("plan verification run", Intent.PLAN_VERIFICATION_RUN, 0.97),
    _GrammarEntry("replay symbol", Intent.REPLAY_SYMBOL, 0.94),
    _GrammarEntry("replay latest signal", Intent.REPLAY_LATEST_SIGNAL, 0.97),
    _GrammarEntry("replay live vs backtest", Intent.REPLAY_LIVE_VS_BACKTEST, 0.94),
    _GrammarEntry("verify top hypothesis", Intent.VERIFY_TOP_HYPOTHESIS, 0.97),
    _GrammarEntry("verify all hypotheses", Intent.VERIFY_ALL_HYPOTHESES, 0.97),
    _GrammarEntry("show replay timeline", Intent.SHOW_REPLAY_TIMELINE, 0.97),
    _GrammarEntry("show replay diff", Intent.SHOW_REPLAY_DIFF, 0.94),
    _GrammarEntry("build verification fixture", Intent.BUILD_VERIFICATION_FIXTURE, 0.94),
    _GrammarEntry("export replay snapshot", Intent.EXPORT_REPLAY_SNAPSHOT, 0.94),
    _GrammarEntry("trace signal lifecycle", Intent.TRACE_SIGNAL_LIFECYCLE, 0.94),
    _GrammarEntry("trace execution lifecycle", Intent.TRACE_EXECUTION_LIFECYCLE, 0.94),
    _GrammarEntry("show causality graph", Intent.SHOW_CAUSALITY_GRAPH, 0.94),
    _GrammarEntry("investigation confidence report", Intent.INVESTIGATION_CONFIDENCE_REPORT, 0.97),
    _GrammarEntry("simulate patch for top hypothesis", Intent.SIMULATE_PATCH_TOP_HYPOTHESIS, 0.97),
    _GrammarEntry("run patch simulation", Intent.RUN_PATCH_SIMULATION, 0.97),
    _GrammarEntry("compare replay before after", Intent.COMPARE_REPLAY_BEFORE_AFTER, 0.97),
    _GrammarEntry("estimate patch impact", Intent.ESTIMATE_PATCH_IMPACT, 0.97),
    _GrammarEntry("generate patch simulation report", Intent.GENERATE_PATCH_SIMULATION_REPORT, 0.97),
    _GrammarEntry("show patch simulation", Intent.SHOW_PATCH_SIMULATION, 0.97),
    _GrammarEntry("approve patch apply", Intent.APPROVE_PATCH_APPLY, 0.97),
    _GrammarEntry("reject patch apply", Intent.REJECT_PATCH_APPLY, 0.97),
    _GrammarEntry("run historical validation sweep", Intent.RUN_HISTORICAL_VALIDATION_SWEEP, 0.97),
    _GrammarEntry("show validation sweep", Intent.SHOW_VALIDATION_SWEEP, 0.97),
    _GrammarEntry("export validation sweep", Intent.EXPORT_VALIDATION_SWEEP, 0.97),
    _GrammarEntry("compare strategy metrics before after", Intent.COMPARE_STRATEGY_METRICS_BEFORE_AFTER, 0.97),
    _GrammarEntry("show worst divergence symbols", Intent.SHOW_WORST_DIVERGENCE_SYMBOLS, 0.97),
    _GrammarEntry("estimate production risk", Intent.ESTIMATE_PRODUCTION_RISK, 0.97),
    _GrammarEntry("recommend production action", Intent.RECOMMEND_PRODUCTION_ACTION, 0.97),
    _GrammarEntry("show investigation summary", Intent.SHOW_INVESTIGATION_SUMMARY, 0.97),
    _GrammarEntry("audit price integrity", Intent.AUDIT_PRICE_INTEGRITY, 0.97),
    _GrammarEntry("compare candle sources", Intent.COMPARE_CANDLE_SOURCES, 0.97),
    _GrammarEntry("trace price source", Intent.TRACE_PRICE_SOURCE, 0.94),
    _GrammarEntry("find close price mismatches", Intent.FIND_CLOSE_PRICE_MISMATCHES, 0.97),
    _GrammarEntry("inspect data cache drift", Intent.INSPECT_DATA_CACHE_DRIFT, 0.97),
    _GrammarEntry("check timestamp alignment", Intent.CHECK_TIMESTAMP_ALIGNMENT, 0.97),
    _GrammarEntry("check adjusted price usage", Intent.CHECK_ADJUSTED_PRICE_USAGE, 0.97),
    _GrammarEntry("check duplicate bars", Intent.CHECK_DUPLICATE_BARS, 0.97),
    _GrammarEntry("generate price integrity report", Intent.GENERATE_PRICE_INTEGRITY_REPORT, 0.97),
    _GrammarEntry("audit execution path", Intent.AUDIT_EXECUTION_PATH, 0.97),
    _GrammarEntry("explain zero execution attempts", Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS, 0.97),
    _GrammarEntry("trace signal to order", Intent.TRACE_SIGNAL_TO_ORDER, 0.94),
    _GrammarEntry("show execution blockers", Intent.SHOW_EXECUTION_BLOCKERS, 0.97),
    _GrammarEntry("rank execution block reasons", Intent.RANK_EXECUTION_BLOCK_REASONS, 0.97),
    _GrammarEntry("inspect execution adapter", Intent.INSPECT_EXECUTION_ADAPTER, 0.97),
    _GrammarEntry("compare signal count to order attempts", Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS, 0.97),
    _GrammarEntry("generate execution investigation report", Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT, 0.97),
    _GrammarEntry("trace signal to execution", Intent.TRACE_SIGNAL_TO_EXECUTION, 0.94),
    _GrammarEntry("trace blocked signal", Intent.TRACE_BLOCKED_SIGNAL, 0.94),
    _GrammarEntry("explain top execution blocker", Intent.EXPLAIN_TOP_EXECUTION_BLOCKER, 0.97),
    _GrammarEntry("reconstruct execution flow", Intent.RECONSTRUCT_EXECUTION_FLOW, 0.97),
    _GrammarEntry("show signal lifecycle timeline", Intent.SHOW_SIGNAL_LIFECYCLE_TIMELINE, 0.97),
    _GrammarEntry("rank dead signal causes", Intent.RANK_DEAD_SIGNAL_CAUSES, 0.97),
    _GrammarEntry("simulate unblock scenario", Intent.SIMULATE_UNBLOCK_SCENARIO, 0.94),
    _GrammarEntry("propose execution fix", Intent.PROPOSE_EXECUTION_FIX, 0.97),
    _GrammarEntry("generate execution flow report", Intent.GENERATE_EXECUTION_FLOW_REPORT, 0.97),
    _GrammarEntry("simulate execution cleanup patch", Intent.SIMULATE_EXECUTION_CLEANUP_PATCH, 0.97),
    _GrammarEntry("compare risk before after cleanup", Intent.COMPARE_RISK_BEFORE_AFTER_CLEANUP, 0.97),
    _GrammarEntry("show stale open positions", Intent.SHOW_STALE_OPEN_POSITIONS, 0.97),
    _GrammarEntry("propose execution cleanup patch", Intent.PROPOSE_EXECUTION_CLEANUP_PATCH, 0.97),
    _GrammarEntry("generate execution cleanup report", Intent.GENERATE_EXECUTION_CLEANUP_REPORT, 0.97),
    _GrammarEntry("show approved patch", Intent.SHOW_APPROVED_PATCH, 0.97),
    _GrammarEntry("validate patch safety", Intent.VALIDATE_PATCH_SAFETY, 0.97),
    _GrammarEntry("validate patch safe", Intent.VALIDATE_PATCH_SAFETY, 0.97),
    _GrammarEntry("apply approved patch", Intent.APPLY_APPROVED_PATCH, 0.97),
    _GrammarEntry("apply approved patch confirm", Intent.APPLY_APPROVED_PATCH, 0.97),
    _GrammarEntry("rollback last patch", Intent.ROLLBACK_LAST_PATCH, 0.97),
    _GrammarEntry("rollback last patch confirm", Intent.ROLLBACK_LAST_PATCH, 0.97),
    _GrammarEntry("show patch history", Intent.SHOW_PATCH_HISTORY, 0.97),
    _GrammarEntry("validate applied patch", Intent.VALIDATE_APPLIED_PATCH, 0.97),
    _GrammarEntry("replay after patch", Intent.REPLAY_AFTER_PATCH, 0.97),
    _GrammarEntry("replay validation", Intent.REPLAY_AFTER_PATCH, 0.97),
    _GrammarEntry("compare pre post patch", Intent.COMPARE_PRE_POST_PATCH, 0.97),
    _GrammarEntry("run patch workflow", Intent.RUN_PATCH_WORKFLOW, 0.97),
    _GrammarEntry("run patch workflow confirm", Intent.RUN_PATCH_WORKFLOW, 0.97),
    _GrammarEntry("show patch workflow status", Intent.SHOW_PATCH_WORKFLOW_STATUS, 0.97),
    _GrammarEntry("phase 49 status", Intent.PHASE49_STATUS, 0.99),
    _GrammarEntry("phase 50 status", Intent.PHASE50_STATUS, 0.99),
    _GrammarEntry("what windows are open", Intent.SHOW_OPEN_WINDOWS, 0.99),
    _GrammarEntry("show open windows", Intent.SHOW_OPEN_WINDOWS, 0.99),
    _GrammarEntry("show screen system status", Intent.SHOW_SCREEN_SYSTEM_STATUS, 0.99),
    _GrammarEntry("show trading operations dashboard", Intent.SHOW_TRADING_OPERATIONS_DASHBOARD, 0.99),
    _GrammarEntry("show running tasks", Intent.SHOW_RUNNING_TASKS, 0.99),
    _GrammarEntry("show completed tasks", Intent.SHOW_COMPLETED_TASKS, 0.99),
    _GrammarEntry("show failed tasks", Intent.SHOW_FAILED_TASKS, 0.99),
    _GrammarEntry("rerun last task", Intent.RERUN_LAST_BACKGROUND_TASK, 0.99),
    _GrammarEntry("show recent results", Intent.SHOW_RECENT_RESULTS, 0.99),
    _GrammarEntry("show notifications", Intent.SHOW_NOTIFICATIONS, 0.99),
    _GrammarEntry("clear notifications", Intent.CLEAR_NOTIFICATIONS, 0.99),
    _GrammarEntry("explain last result", Intent.EXPLAIN_LAST_RESULT, 0.99),
    _GrammarEntry("continue previous session", Intent.CONTINUE_PREVIOUS_SESSION, 0.99),
    _GrammarEntry("summarize unresolved issues", Intent.SUMMARIZE_UNRESOLVED_ISSUES, 0.99),
    _GrammarEntry("resume latest investigation", Intent.RESUME_LATEST_INVESTIGATION, 0.99),
    _GrammarEntry("what changed since last session", Intent.WHAT_CHANGED_SINCE_LAST_SESSION, 0.99),
    _GrammarEntry("summarize system intelligence", Intent.SUMMARIZE_SYSTEM_INTELLIGENCE, 0.99),
    _GrammarEntry("summarize unresolved blockers", Intent.SUMMARIZE_UNRESOLVED_BLOCKERS, 0.99),
    _GrammarEntry("explain current operational state", Intent.EXPLAIN_CURRENT_OPERATIONAL_STATE, 0.99),
    _GrammarEntry("recommend next action", Intent.RECOMMEND_NEXT_ACTION, 0.99),
    _GrammarEntry("what should we investigate next", Intent.WHAT_SHOULD_WE_INVESTIGATE_NEXT, 0.99),
    _GrammarEntry("show investigation schedule", Intent.SHOW_INVESTIGATION_SCHEDULE, 0.99),
    _GrammarEntry("run investigation cycle", Intent.RUN_INVESTIGATION_CYCLE, 0.99),
    _GrammarEntry("pause investigation loop", Intent.PAUSE_INVESTIGATION_LOOP, 0.99),
    _GrammarEntry("resume investigation loop", Intent.RESUME_INVESTIGATION_LOOP, 0.99),
    _GrammarEntry("run nightly investigation now", Intent.RUN_NIGHTLY_INVESTIGATION_NOW, 0.99),
    _GrammarEntry("show blocker trends", Intent.SHOW_BLOCKER_TRENDS, 0.99),
    _GrammarEntry("show active hypotheses", Intent.SHOW_ACTIVE_HYPOTHESES, 0.99),
    _GrammarEntry("explain top hypothesis", Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS, 0.99),
    _GrammarEntry("show intelligence timeline", Intent.SHOW_INTELLIGENCE_TIMELINE, 0.99),
    _GrammarEntry("summarize autonomous findings", Intent.SUMMARIZE_AUTONOMOUS_FINDINGS, 0.99),
    _GrammarEntry("summarize root causes", Intent.SUMMARIZE_ROOT_CAUSES, 0.99),
    _GrammarEntry("verify root causes", Intent.VERIFY_ROOT_CAUSES, 0.99),
    _GrammarEntry("show verification plans", Intent.SHOW_VERIFICATION_PLANS, 0.99),
    _GrammarEntry("show confidence evolution", Intent.SHOW_CONFIDENCE_EVOLUTION, 0.99),
    _GrammarEntry("show contradictory evidence", Intent.SHOW_CONTRADICTORY_EVIDENCE, 0.99),
    _GrammarEntry("suggest experiments", Intent.SUGGEST_EXPERIMENTS, 0.99),
    _GrammarEntry("show root cause graph", Intent.SHOW_ROOT_CAUSE_GRAPH, 0.99),
    _GrammarEntry("trace causal chain", Intent.TRACE_CAUSAL_CHAIN, 0.99),
    _GrammarEntry("explain dominant root cause", Intent.EXPLAIN_DOMINANT_ROOT_CAUSE, 0.99),
    _GrammarEntry("explain why trades are blocked", Intent.EXPLAIN_WHY_TRADES_ARE_BLOCKED, 0.99),
    _GrammarEntry("show runtime health", Intent.SHOW_RUNTIME_HEALTH, 0.99),
    _GrammarEntry("show healing actions", Intent.SHOW_HEALING_ACTIONS, 0.99),
    _GrammarEntry("show stuck workers", Intent.SHOW_STUCK_WORKERS, 0.99),
    _GrammarEntry("validate runtime integrity", Intent.VALIDATE_RUNTIME_INTEGRITY, 0.99),
    _GrammarEntry("summarize trading health", Intent.SUMMARIZE_TRADING_HEALTH, 0.99),
    _GrammarEntry("summarize current screen", Intent.SUMMARIZE_CURRENT_SCREEN, 0.99),
    _GrammarEntry("summarize my screen", Intent.SUMMARIZE_CURRENT_SCREEN, 0.99),
    _GrammarEntry("what am i looking at", Intent.WHAT_AM_I_LOOKING_AT, 0.99),
    _GrammarEntry("resume last task", Intent.RESUME_LAST_TASK, 0.99),
    _GrammarEntry("what was i doing", Intent.RESUME_LAST_TASK, 0.98),
    _GrammarEntry("show operational suggestions", Intent.SHOW_OPERATIONAL_SUGGESTIONS, 0.99),
    _GrammarEntry("show current state", Intent.SHOW_CURRENT_STATE, 0.99),
    _GrammarEntry("show runtime summary", Intent.SHOW_RUNTIME_SUMMARY, 0.99),
    _GrammarEntry("open last report", Intent.OPEN_LAST_REPORT, 0.99),
    _GrammarEntry("open latest report", Intent.OPEN_LAST_REPORT, 0.99),
    _GrammarEntry("benchmark voice modes", Intent.BENCHMARK_VOICE_MODES, 0.96),
    _GrammarEntry("voice smoke test", Intent.VOICE_SMOKE_TEST, 0.96),
    _GrammarEntry("show system status", Intent.SHOW_SYSTEM_STATUS, 0.96),
    _GrammarEntry("show voice performance status", Intent.SHOW_VOICE_PERFORMANCE_STATUS, 0.96),
    _GrammarEntry("show voice debug", Intent.SHOW_VOICE_DEBUG, 0.96),
    _GrammarEntry("show audio status", Intent.SHOW_AUDIO_STATUS, 0.96),
    _GrammarEntry("tool mode status", Intent.TOOL_MODE_STATUS, 0.96),
    _GrammarEntry("test voice output", Intent.TEST_VOICE_OUTPUT, 0.96),
    _GrammarEntry("test direct speech", Intent.TEST_DIRECT_SPEECH, 0.96),
    _GrammarEntry("verify direct speech backend", Intent.VERIFY_DIRECT_SPEECH_BACKEND, 0.96),
    _GrammarEntry(
        "force verified direct speech confirm",
        Intent.FORCE_VERIFIED_DIRECT_SPEECH,
        0.96,
    ),
    _GrammarEntry("test normal speech path", Intent.TEST_NORMAL_SPEECH, 0.96),
    _GrammarEntry("audio route prove", Intent.AUDIO_ROUTE_PROVE, 0.96),
    _GrammarEntry(
        "force direct pyttsx3 normal mode",
        Intent.FORCE_DIRECT_PYTTSX3_NORMAL_MODE,
        0.96,
    ),
    _GrammarEntry("test subprocess speech", Intent.TEST_SUBPROCESS_SPEECH, 0.96),
    _GrammarEntry(
        "show windows audio routing",
        Intent.SHOW_WINDOWS_AUDIO_ROUTING,
        0.96,
    ),
    _GrammarEntry(
        "cycle windows playback target",
        Intent.CYCLE_WINDOWS_PLAYBACK_TARGET,
        0.96,
    ),
    _GrammarEntry("stop speech hard", Intent.STOP_SPEECH_HARD, 0.96),
    _GrammarEntry("force shell tts test", Intent.FORCE_SHELL_TTS_TEST, 0.96),
    _GrammarEntry("show me the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _GrammarEntry("bring up the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _GrammarEntry("open the dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _GrammarEntry("open dashboard", Intent.OPEN_TRADING_DASHBOARD, 0.96),
    _GrammarEntry("open dashboard url", Intent.OPEN_TRADING_DASHBOARD_URL, 0.97),
    _GrammarEntry("open chrome", Intent.OPEN_CHROME, 0.96),
    _GrammarEntry("open cursor", Intent.OPEN_CURSOR, 0.96),
    _GrammarEntry("open discord", Intent.OPEN_APP, 0.95, {"app": "discord"}),
    _GrammarEntry("open youtube", Intent.OPEN_WEBSITE, 0.95, {"website": "youtube"}),
    _GrammarEntry("open chatgpt", Intent.OPEN_WEBSITE, 0.95, {"website": "chatgpt"}),
    _GrammarEntry("open tradingview", Intent.OPEN_WEBSITE, 0.95, {"website": "tradingview"}),
    _GrammarEntry("what is on my screen", Intent.WHAT_IS_ON_MY_SCREEN, 0.95),
    _GrammarEntry("summarize this screen", Intent.SUMMARIZE_THIS_SCREEN, 0.95),
    _GrammarEntry("click the button that says", Intent.CLICK_BUTTON_THAT_SAYS, 0.95),
    _GrammarEntry("type this", Intent.TYPE_THIS, 0.95),
    _GrammarEntry("switch to chrome", Intent.SWITCH_TO_CHROME, 0.95),
    _GrammarEntry("list open windows", Intent.LIST_OPEN_WINDOWS, 0.95),
    _GrammarEntry("search web for", Intent.SEARCH_WEB_FOR, 0.95),
    _GrammarEntry("find information about", Intent.FIND_INFORMATION_ABOUT, 0.95),
    _GrammarEntry("open the best result", Intent.OPEN_BEST_RESULT, 0.95),
    _GrammarEntry("summarize the top results", Intent.SUMMARIZE_TOP_RESULTS, 0.95),
    _GrammarEntry("compare these search results", Intent.COMPARE_THESE_SEARCH_RESULTS, 0.95),
    _GrammarEntry("extract key facts from this page", Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE, 0.95),
    _GrammarEntry("save browser research report", Intent.SAVE_BROWSER_RESEARCH_REPORT, 0.95),
    _GrammarEntry("summarize this page", Intent.SUMMARIZE_THIS_PAGE, 0.95),
    _GrammarEntry("compare these results", Intent.COMPARE_THESE_RESULTS, 0.95),
    _GrammarEntry("compare these pages", Intent.COMPARE_THESE_PAGES, 0.95),
    _GrammarEntry("what tab is active", Intent.WHAT_TAB_IS_ACTIVE, 0.95),
    _GrammarEntry("what page am i on", Intent.WHAT_TAB_IS_ACTIVE, 0.95),
    _GrammarEntry("show browser debug", Intent.SHOW_BROWSER_DEBUG, 0.95),
    _GrammarEntry("open browser", Intent.OPEN_BROWSER, 0.95),
    _GrammarEntry("test real browser", Intent.TEST_REAL_BROWSER, 0.95),
    _GrammarEntry("summarize current page", Intent.SUMMARIZE_THIS_PAGE, 0.95),
    _GrammarEntry("show runtime config mismatches", Intent.SHOW_RUNTIME_CONFIG_MISMATCHES, 0.95),
    _GrammarEntry("show capability health", Intent.SHOW_CAPABILITY_HEALTH, 0.95),
    _GrammarEntry("show voice health", Intent.SHOW_VOICE_HEALTH, 0.95),
    _GrammarEntry("repair memory store", Intent.REPAIR_MEMORY_STORE, 0.95),
    _GrammarEntry("show browser health", Intent.SHOW_BROWSER_HEALTH, 0.95),
    _GrammarEntry("show system health", Intent.SHOW_SYSTEM_HEALTH, 0.95),
    _GrammarEntry("show performance report", Intent.SHOW_PERFORMANCE_REPORT, 0.95),
    _GrammarEntry("summarize my inbox", Intent.SUMMARIZE_MY_INBOX, 0.95),
    _GrammarEntry("show urgent emails", Intent.SHOW_URGENT_EMAILS, 0.95),
    _GrammarEntry("summarize my calendar", Intent.SUMMARIZE_MY_CALENDAR, 0.95),
    _GrammarEntry("summarize my day", Intent.SUMMARIZE_MY_DAY, 0.95),
    _GrammarEntry("summarize my last 100 emails", Intent.SUMMARIZE_MY_LAST_100_EMAILS, 0.95),
    _GrammarEntry("what needs my attention today", Intent.WHAT_NEEDS_MY_ATTENTION_TODAY, 0.95),
    _GrammarEntry("find calendar conflicts", Intent.FIND_CALENDAR_CONFLICTS, 0.95),
    _GrammarEntry("show memory debug", Intent.SHOW_MEMORY_DEBUG, 0.95),
    _GrammarEntry("what is on my screen", Intent.DESCRIBE_SCREEN, 0.95),
    _GrammarEntry("whats on my screen", Intent.DESCRIBE_SCREEN, 0.95),
    _GrammarEntry("describe the screen", Intent.DESCRIBE_SCREEN, 0.95),
    _GrammarEntry("describe screen", Intent.DESCRIBE_SCREEN, 0.95),
    _GrammarEntry("read screen text", Intent.READ_SCREEN_TEXT, 0.94),
    _GrammarEntry("analyze this window", Intent.ANALYZE_ACTIVE_WINDOW, 0.95),
    _GrammarEntry("look at this window", Intent.ANALYZE_ACTIVE_WINDOW, 0.95),
    _GrammarEntry("analyze active window", Intent.ANALYZE_ACTIVE_WINDOW, 0.95),
    _GrammarEntry("what am i doing", Intent.WHAT_AM_I_DOING, 0.95),
    _GrammarEntry("what were we doing", Intent.WHAT_WERE_WE_DOING, 0.95),
    _GrammarEntry("summarize session", Intent.SUMMARIZE_SESSION, 0.95),
    _GrammarEntry("review latest patch", Intent.REVIEW_LATEST_PATCH, 0.94),
    _GrammarEntry("show failing tests", Intent.SHOW_FAILING_TESTS, 0.94),
    _GrammarEntry("explain this error", Intent.EXPLAIN_THIS_ERROR, 0.94),
    _GrammarEntry("make a plan", Intent.ASSISTANT_PLAN, 0.94),
    _GrammarEntry("assistant plan", Intent.ASSISTANT_PLAN, 0.94),
    _GrammarEntry("show memory graph", Intent.SHOW_MEMORY_GRAPH, 0.94),
    _GrammarEntry("diagnose voice runtime", Intent.DIAGNOSE_VOICE_RUNTIME, 0.96),
    _GrammarEntry("reset jarvis runtime", Intent.RESET_JARVIS_RUNTIME, 0.96),
    _GrammarEntry("show jarvis status", Intent.SHOW_JARVIS_STATUS, 0.96),
    _GrammarEntry("show voice latency budget", Intent.SHOW_LATENCY_STATUS, 0.96),
    _GrammarEntry("run diagnostics", Intent.RUN_DIAGNOSTICS, 0.95),
    _GrammarEntry("show me diagnostics", Intent.RUN_DIAGNOSTICS, 0.95),
    _GrammarEntry("show dashboard health", Intent.SHOW_DASHBOARD_HEALTH, 0.96),
    _GrammarEntry("show runtime status", Intent.SHOW_RUNTIME_STATUS, 0.96),
    _GrammarEntry("show wake diagnostics", Intent.SHOW_WAKE_DIAGNOSTICS, 0.96),
    _GrammarEntry("show last errors", Intent.SHOW_LAST_ERRORS, 0.96),
    _GrammarEntry("list workflows", Intent.LIST_WORKFLOWS, 0.95),
    _GrammarEntry("check trading", Intent.RUN_WORKFLOW, 0.94, {"workflow": "trading_health_check"}),
    _GrammarEntry("calibrate voice", Intent.CALIBRATE_VOICE, 0.96),
    _GrammarEntry("auto tune voice", Intent.AUTO_TUNE_VOICE, 0.95),
    _GrammarEntry("show stt stack status", Intent.SHOW_STT_STACK_STATUS, 0.96),
    _GrammarEntry("show stt status", Intent.SHOW_STT_STATUS, 0.95),
    _GrammarEntry("show tts status", Intent.SHOW_TTS_STATUS, 0.95),
    _GrammarEntry("show tts debug", Intent.SHOW_TTS_DEBUG, 0.96),
    _GrammarEntry("test tts playback", Intent.TEST_TTS_PLAYBACK, 0.96),
    _GrammarEntry("test direct tts", Intent.TEST_DIRECT_TTS, 0.96),
    _GrammarEntry("test streaming stt", Intent.TEST_STREAMING_STT, 0.96),
    _GrammarEntry("show capabilities", Intent.SHOW_CAPABILITIES, 0.94),
    _GrammarEntry("what can you do", Intent.SHOW_CAPABILITIES, 0.94),
]


def _grammar_compatible(normalized: str, phrase: str) -> bool:
    if "stt" in normalized and "tts" in phrase:
        return False
    if "tts" in normalized and "stt" in phrase:
        return False
    if "speech" in normalized and "screen" in phrase:
        return False
    if "screen" in normalized and "speech" in phrase:
        return False
    if " url" in phrase and "url" not in normalized:
        return False
    if phrase.endswith(" url") and not normalized.endswith("url"):
        return False
    if "performance" in normalized and "performance" not in phrase and "voice" in phrase:
        return False
    if "performance" in phrase and "performance" not in normalized:
        return False
    return True


def _normalize(text: str) -> str:
    import re
    import unicodedata

    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.split())


def score_command_grammar(
    text: str,
    *,
    min_score: int | None = None,
) -> GrammarMatchResult | None:
    """
    Score transcript against known command phrases.
    Returns None if rapidfuzz unavailable or below threshold.
    """
    if fuzz is None:
        return None
    normalized = _normalize(text)
    if not normalized:
        return None
    threshold = VOICE_GRAMMAR_MIN_SCORE if min_score is None else min_score
    best_entry: _GrammarEntry | None = None
    best_score = 0
    best_len = 0
    best_contained = False
    for entry in sorted(_COMMAND_GRAMMAR, key=lambda e: len(e.phrase), reverse=True):
        if not _grammar_compatible(normalized, entry.phrase):
            continue
        phrase = entry.phrase
        if normalized == phrase:
            score = 100
        else:
            scores = [
                int(fuzz.ratio(normalized, phrase)),
                int(fuzz.token_sort_ratio(normalized, phrase)),
            ]
            if phrase in normalized:
                scores.append(int(fuzz.partial_ratio(normalized, phrase)))
            score = max(scores)
        phrase_len = len(entry.phrase)
        contained = phrase in normalized or normalized == phrase
        if score >= threshold and (
            score > best_score
            or (score == best_score and contained and not best_contained)
            or (score == best_score and contained == best_contained and phrase_len > best_len)
        ):
            best_score = score
            best_len = phrase_len
            best_contained = contained
            best_entry = entry
    if best_entry is None:
        return None
    conf = min(0.99, best_entry.confidence * (best_score / 100.0))
    reason = "exact_phrase" if best_score >= 99 else "fuzzy_grammar_match"
    corrected = best_entry.phrase
    return GrammarMatchResult(
        best_command=best_entry.intent.value,
        intent=best_entry.intent,
        confidence=conf,
        matched_phrase=best_entry.phrase,
        correction_reason=reason,
        corrected_text=corrected,
        fuzzy_score=best_score,
    )


def apply_grammar_correction(
    text: str,
    *,
    min_score: int | None = None,
) -> tuple[str, GrammarMatchResult | None]:
    """Return (text_for_classifier, grammar_match). Does not execute commands."""
    match = score_command_grammar(text, min_score=min_score)
    if match is None:
        return text, None
    if match.fuzzy_score >= 92 or match.correction_reason == "exact_phrase":
        return match.corrected_text, match
    return text, match


def grammar_to_command_request(text: str, match: GrammarMatchResult) -> CommandRequest:
    entry = next((e for e in _COMMAND_GRAMMAR if e.phrase == match.matched_phrase), None)
    params = dict(entry.params) if entry and entry.params else {}
    return CommandRequest(
        raw_text=text,
        intent=match.intent,
        confidence=match.confidence,
        params=params,
        language="en",
        classifier_source="command_grammar",
    )


def match_command_grammar_as_request(
    text: str,
    *,
    min_score: int | None = None,
) -> CommandRequest | None:
    """Compatibility helper for intent_classifier."""
    match = score_command_grammar(text, min_score=min_score)
    if match is None:
        return None
    return grammar_to_command_request(text, match)


def list_grammar_phrases() -> list[str]:
    return sorted({e.phrase for e in _COMMAND_GRAMMAR})
