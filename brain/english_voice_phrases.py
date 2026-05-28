"""Natural English voice phrase → intent mappings (rules only, no execution)."""

from __future__ import annotations

import re
import unicodedata

from core.types import CommandRequest, Intent

# (phrases, intent, confidence, optional params)
_ENGLISH_VOICE_PHRASES: list[tuple[list[str], Intent, float, dict | None]] = [
    (
        ["open dashboard url"],
        Intent.OPEN_TRADING_DASHBOARD_URL,
        0.97,
        None,
    ),
    (
        [
            "open dashboard",
            "open the dashboard",
            "open trading dashboard",
            "show dashboard",
            "can you open the dashboard",
            "bring up the dashboard",
        ],
        Intent.OPEN_TRADING_DASHBOARD,
        0.95,
        None,
    ),
    (
        [
            "check the dashboard",
            "is the dashboard running",
            "is dashboard running",
            "dashboard health check",
        ],
        Intent.SHOW_DASHBOARD_HEALTH,
        0.95,
        None,
    ),
    (
        ["run a system check", "run system check", "system check"],
        Intent.RUN_DIAGNOSTICS,
        0.94,
        None,
    ),
    (
        ["what is wrong", "what's wrong", "something is wrong"],
        Intent.RUN_DIAGNOSTICS,
        0.92,
        None,
    ),
    (
        [
            "check trading",
            "check my trading system",
            "check the trading system",
            "trading health check",
            "run trading health check",
        ],
        Intent.RUN_WORKFLOW,
        0.94,
        {"workflow": "trading_health_check"},
    ),
    (
        ["show me the errors", "show the errors", "show me errors"],
        Intent.SHOW_LAST_ERRORS,
        0.94,
        None,
    ),
    (
        ["what can you do", "what can jarvis do"],
        Intent.SHOW_CAPABILITIES,
        0.95,
        None,
    ),
    (
        ["are you working", "can you hear me"],
        Intent.SHOW_JARVIS_STATUS,
        0.95,
        None,
    ),
    (
        ["show voice status", "show speech status", "voice status", "speech status"],
        Intent.SHOW_STT_STATUS,
        0.95,
        None,
    ),
    (
        ["show stt status", "stt status"],
        Intent.SHOW_STT_STATUS,
        0.96,
        None,
    ),
    (
        ["benchmark stt", "stt benchmark"],
        Intent.BENCHMARK_STT,
        0.94,
        None,
    ),
    (
        ["show tts status", "tts status", "voice output status"],
        Intent.SHOW_TTS_STATUS,
        0.96,
        None,
    ),
    (
        ["show tts debug", "tts debug", "tts output debug"],
        Intent.SHOW_TTS_DEBUG,
        0.96,
        None,
    ),
    (
        ["test tts playback", "tts playback test", "playback test"],
        Intent.TEST_TTS_PLAYBACK,
        0.96,
        None,
    ),
    (
        ["test direct tts", "direct tts test"],
        Intent.TEST_DIRECT_TTS,
        0.96,
        None,
    ),
    (
        ["test streaming stt", "streaming stt test"],
        Intent.TEST_STREAMING_STT,
        0.96,
        None,
    ),
    (
        [
            "show voice debug",
            "voice debug",
            "speech debug",
            "what did you hear",
            "show what you heard",
        ],
        Intent.SHOW_VOICE_DEBUG,
        0.96,
        None,
    ),
    (
        ["show audio status", "audio status", "playback status"],
        Intent.SHOW_AUDIO_STATUS,
        0.96,
        None,
    ),
    (
        ["tool mode status", "show tool mode status", "tool first status"],
        Intent.TOOL_MODE_STATUS,
        0.96,
        None,
    ),
    (["phase 45 status", "phase45 status"], Intent.PHASE45_STATUS, 0.97, None),
    (["phase 46 status", "phase46 status"], Intent.PHASE46_STATUS, 0.97, None),
    (["inspect project"], Intent.INSPECT_PROJECT, 0.97, None),
    (
        ["inspect website project", "audit website project", "website project audit"],
        Intent.INSPECT_WEBSITE_PROJECT,
        0.97,
        None,
    ),
    (["show memory debug"], Intent.SHOW_MEMORY_DEBUG, 0.96, None),
    (
        ["what do you remember about", "what do you remember on"],
        Intent.SEARCH_MEMORY,
        0.95,
        None,
    ),
    (["show browser debug"], Intent.SHOW_BROWSER_DEBUG, 0.96, None),
    (["open browser"], Intent.OPEN_BROWSER, 0.96, None),
    (["test real browser"], Intent.TEST_REAL_BROWSER, 0.96, None),
    (["show runtime config mismatches"], Intent.SHOW_RUNTIME_CONFIG_MISMATCHES, 0.96, None),
    (["show capability health"], Intent.SHOW_CAPABILITY_HEALTH, 0.96, None),
    (["show voice health"], Intent.SHOW_VOICE_HEALTH, 0.96, None),
    (["repair memory store"], Intent.REPAIR_MEMORY_STORE, 0.96, None),
    (["show browser health"], Intent.SHOW_BROWSER_HEALTH, 0.96, None),
    (["show system health"], Intent.SHOW_SYSTEM_HEALTH, 0.96, None),
    (["show performance report"], Intent.SHOW_PERFORMANCE_REPORT, 0.96, None),
    (["summarize my inbox"], Intent.SUMMARIZE_MY_INBOX, 0.96, None),
    (["show urgent emails"], Intent.SHOW_URGENT_EMAILS, 0.96, None),
    (["summarize my calendar"], Intent.SUMMARIZE_MY_CALENDAR, 0.96, None),
    (["what is on my screen"], Intent.WHAT_IS_ON_MY_SCREEN, 0.96, None),
    (["summarize this screen"], Intent.SUMMARIZE_THIS_SCREEN, 0.96, None),
    (["click the button that says"], Intent.CLICK_BUTTON_THAT_SAYS, 0.96, None),
    (["type this"], Intent.TYPE_THIS, 0.96, None),
    (["switch to chrome"], Intent.SWITCH_TO_CHROME, 0.96, None),
    (["list open windows"], Intent.LIST_OPEN_WINDOWS, 0.96, None),
    (["search web for"], Intent.SEARCH_WEB_FOR, 0.96, None),
    (["find information about"], Intent.FIND_INFORMATION_ABOUT, 0.96, None),
    (["open the best result"], Intent.OPEN_BEST_RESULT, 0.96, None),
    (["summarize the top results"], Intent.SUMMARIZE_TOP_RESULTS, 0.96, None),
    (["compare these search results"], Intent.COMPARE_THESE_SEARCH_RESULTS, 0.96, None),
    (["extract key facts from this page"], Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE, 0.96, None),
    (["save browser research report"], Intent.SAVE_BROWSER_RESEARCH_REPORT, 0.96, None),
    (["summarize this page"], Intent.SUMMARIZE_THIS_PAGE, 0.96, None),
    (["summarize current page"], Intent.SUMMARIZE_THIS_PAGE, 0.96, None),
    (["compare these results"], Intent.COMPARE_THESE_RESULTS, 0.96, None),
    (["compare these pages"], Intent.COMPARE_THESE_PAGES, 0.96, None),
    (["what tab is active"], Intent.WHAT_TAB_IS_ACTIVE, 0.96, None),
    (["what page am i on"], Intent.WHAT_TAB_IS_ACTIVE, 0.96, None),
    (["summarize my day"], Intent.SUMMARIZE_MY_DAY, 0.96, None),
    (
        ["summarize my last 100 emails", "summarize last 100 emails"],
        Intent.SUMMARIZE_MY_LAST_100_EMAILS,
        0.96,
        None,
    ),
    (
        ["what needs my attention today"],
        Intent.WHAT_NEEDS_MY_ATTENTION_TODAY,
        0.96,
        None,
    ),
    (["find calendar conflicts"], Intent.FIND_CALENDAR_CONFLICTS, 0.96, None),
    (["summarize current project"], Intent.SUMMARIZE_CURRENT_PROJECT, 0.97, None),
    (["find failing tests"], Intent.FIND_FAILING_TESTS, 0.97, None),
    (["explain latest error"], Intent.EXPLAIN_LATEST_ERROR, 0.97, None),
    (["investigate trading mismatch"], Intent.INVESTIGATE_TRADING_MISMATCH, 0.97, None),
    (["compare live vs backtest", "compare backtest vs live"], Intent.COMPARE_LIVE_VS_BACKTEST, 0.97, None),
    (["inspect latest live report"], Intent.INSPECT_LATEST_LIVE_REPORT, 0.97, None),
    (["inspect latest backtest report"], Intent.INSPECT_LATEST_BACKTEST_REPORT, 0.97, None),
    (["find recent code changes"], Intent.FIND_RECENT_CODE_CHANGES, 0.97, None),
    (["propose investigation plan"], Intent.PROPOSE_INVESTIGATION_PLAN, 0.97, None),
    (["run safe diagnostics"], Intent.RUN_SAFE_DIAGNOSTICS, 0.97, None),
    (["generate findings report"], Intent.GENERATE_FINDINGS_REPORT, 0.97, None),
    (["build investigation graph"], Intent.BUILD_INVESTIGATION_GRAPH, 0.97, None),
    (["show investigation graph"], Intent.SHOW_INVESTIGATION_GRAPH, 0.97, None),
    (["search investigation graph"], Intent.SEARCH_INVESTIGATION_GRAPH, 0.94, None),
    (["trace algorithm behavior"], Intent.TRACE_ALGORITHM_BEHAVIOR, 0.97, None),
    (["diff live and backtest logic"], Intent.DIFF_LIVE_BACKTEST_LOGIC, 0.97, None),
    (["hunt algorithm bugs"], Intent.HUNT_ALGORITHM_BUGS, 0.97, None),
    (["propose algorithm patch"], Intent.PROPOSE_ALGORITHM_PATCH, 0.97, None),
    (["plan verification run"], Intent.PLAN_VERIFICATION_RUN, 0.97, None),
    (["replay symbol"], Intent.REPLAY_SYMBOL, 0.94, None),
    (["replay latest signal"], Intent.REPLAY_LATEST_SIGNAL, 0.97, None),
    (["replay live vs backtest"], Intent.REPLAY_LIVE_VS_BACKTEST, 0.94, None),
    (["verify top hypothesis"], Intent.VERIFY_TOP_HYPOTHESIS, 0.97, None),
    (["verify all hypotheses"], Intent.VERIFY_ALL_HYPOTHESES, 0.97, None),
    (["show replay timeline"], Intent.SHOW_REPLAY_TIMELINE, 0.97, None),
    (["show replay diff"], Intent.SHOW_REPLAY_DIFF, 0.94, None),
    (["build verification fixture"], Intent.BUILD_VERIFICATION_FIXTURE, 0.94, None),
    (["export replay snapshot"], Intent.EXPORT_REPLAY_SNAPSHOT, 0.94, None),
    (["trace signal lifecycle"], Intent.TRACE_SIGNAL_LIFECYCLE, 0.94, None),
    (["trace execution lifecycle"], Intent.TRACE_EXECUTION_LIFECYCLE, 0.94, None),
    (["show causality graph"], Intent.SHOW_CAUSALITY_GRAPH, 0.94, None),
    (["investigation confidence report"], Intent.INVESTIGATION_CONFIDENCE_REPORT, 0.97, None),
    (["simulate patch for top hypothesis"], Intent.SIMULATE_PATCH_TOP_HYPOTHESIS, 0.97, None),
    (["run patch simulation"], Intent.RUN_PATCH_SIMULATION, 0.97, None),
    (["compare replay before after"], Intent.COMPARE_REPLAY_BEFORE_AFTER, 0.97, None),
    (["estimate patch impact"], Intent.ESTIMATE_PATCH_IMPACT, 0.97, None),
    (["generate patch simulation report"], Intent.GENERATE_PATCH_SIMULATION_REPORT, 0.97, None),
    (["show patch simulation"], Intent.SHOW_PATCH_SIMULATION, 0.97, None),
    (["approve patch apply"], Intent.APPROVE_PATCH_APPLY, 0.97, None),
    (["reject patch apply"], Intent.REJECT_PATCH_APPLY, 0.97, None),
    (["run historical validation sweep"], Intent.RUN_HISTORICAL_VALIDATION_SWEEP, 0.97, None),
    (["show validation sweep"], Intent.SHOW_VALIDATION_SWEEP, 0.97, None),
    (["export validation sweep"], Intent.EXPORT_VALIDATION_SWEEP, 0.97, None),
    (["compare strategy metrics before after"], Intent.COMPARE_STRATEGY_METRICS_BEFORE_AFTER, 0.97, None),
    (["show worst divergence symbols"], Intent.SHOW_WORST_DIVERGENCE_SYMBOLS, 0.97, None),
    (["estimate production risk"], Intent.ESTIMATE_PRODUCTION_RISK, 0.97, None),
    (["recommend production action"], Intent.RECOMMEND_PRODUCTION_ACTION, 0.97, None),
    (["show investigation summary"], Intent.SHOW_INVESTIGATION_SUMMARY, 0.97, None),
    (["audit price integrity"], Intent.AUDIT_PRICE_INTEGRITY, 0.97, None),
    (["compare candle sources"], Intent.COMPARE_CANDLE_SOURCES, 0.97, None),
    (["trace price source"], Intent.TRACE_PRICE_SOURCE, 0.94, None),
    (["find close price mismatches"], Intent.FIND_CLOSE_PRICE_MISMATCHES, 0.97, None),
    (["inspect data cache drift"], Intent.INSPECT_DATA_CACHE_DRIFT, 0.97, None),
    (["check timestamp alignment"], Intent.CHECK_TIMESTAMP_ALIGNMENT, 0.97, None),
    (["check adjusted price usage"], Intent.CHECK_ADJUSTED_PRICE_USAGE, 0.97, None),
    (["check duplicate bars"], Intent.CHECK_DUPLICATE_BARS, 0.97, None),
    (["generate price integrity report"], Intent.GENERATE_PRICE_INTEGRITY_REPORT, 0.97, None),
    (["audit execution path"], Intent.AUDIT_EXECUTION_PATH, 0.97, None),
    (["explain zero execution attempts"], Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS, 0.97, None),
    (["trace signal to order"], Intent.TRACE_SIGNAL_TO_ORDER, 0.94, None),
    (["show execution blockers"], Intent.SHOW_EXECUTION_BLOCKERS, 0.97, None),
    (["rank execution block reasons"], Intent.RANK_EXECUTION_BLOCK_REASONS, 0.97, None),
    (["inspect execution adapter"], Intent.INSPECT_EXECUTION_ADAPTER, 0.97, None),
    (["compare signal count to order attempts"], Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS, 0.97, None),
    (["generate execution investigation report"], Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT, 0.97, None),
    (["trace signal to execution"], Intent.TRACE_SIGNAL_TO_EXECUTION, 0.94, None),
    (["trace blocked signal"], Intent.TRACE_BLOCKED_SIGNAL, 0.94, None),
    (["explain top execution blocker"], Intent.EXPLAIN_TOP_EXECUTION_BLOCKER, 0.97, None),
    (["reconstruct execution flow"], Intent.RECONSTRUCT_EXECUTION_FLOW, 0.97, None),
    (["show signal lifecycle timeline"], Intent.SHOW_SIGNAL_LIFECYCLE_TIMELINE, 0.97, None),
    (["rank dead signal causes"], Intent.RANK_DEAD_SIGNAL_CAUSES, 0.97, None),
    (["simulate unblock scenario"], Intent.SIMULATE_UNBLOCK_SCENARIO, 0.94, None),
    (["propose execution fix"], Intent.PROPOSE_EXECUTION_FIX, 0.97, None),
    (["generate execution flow report"], Intent.GENERATE_EXECUTION_FLOW_REPORT, 0.97, None),
    (["simulate execution cleanup patch"], Intent.SIMULATE_EXECUTION_CLEANUP_PATCH, 0.97, None),
    (["compare risk before after cleanup"], Intent.COMPARE_RISK_BEFORE_AFTER_CLEANUP, 0.97, None),
    (["show stale open positions"], Intent.SHOW_STALE_OPEN_POSITIONS, 0.97, None),
    (["propose execution cleanup patch"], Intent.PROPOSE_EXECUTION_CLEANUP_PATCH, 0.97, None),
    (["generate execution cleanup report"], Intent.GENERATE_EXECUTION_CLEANUP_REPORT, 0.97, None),
    (["show approved patch"], Intent.SHOW_APPROVED_PATCH, 0.97, None),
    (["validate patch safety", "validate patch safe"], Intent.VALIDATE_PATCH_SAFETY, 0.97, None),
    (["apply approved patch"], Intent.APPLY_APPROVED_PATCH, 0.97, None),
    (["apply approved patch confirm"], Intent.APPLY_APPROVED_PATCH, 0.97, None),
    (["rollback last patch"], Intent.ROLLBACK_LAST_PATCH, 0.97, None),
    (["rollback last patch confirm"], Intent.ROLLBACK_LAST_PATCH, 0.97, None),
    (["show patch history"], Intent.SHOW_PATCH_HISTORY, 0.97, None),
    (["validate applied patch"], Intent.VALIDATE_APPLIED_PATCH, 0.97, None),
    (["replay after patch", "replay validation", "replay patch validation"], Intent.REPLAY_AFTER_PATCH, 0.97, None),
    (["compare pre post patch", "compare pre and post patch"], Intent.COMPARE_PRE_POST_PATCH, 0.97, None),
    (["run patch workflow"], Intent.RUN_PATCH_WORKFLOW, 0.97, None),
    (["run patch workflow confirm"], Intent.RUN_PATCH_WORKFLOW, 0.97, None),
    (["show patch workflow status", "patch workflow status"], Intent.SHOW_PATCH_WORKFLOW_STATUS, 0.97, None),
    (
        [
            "test voice output",
            "test voice",
            "test audio",
            "test speech",
            "try speaking",
            "say something",
        ],
        Intent.TEST_VOICE_OUTPUT,
        0.96,
        None,
    ),
    (
        ["calibrate voice", "voice calibration", "calibrate speech"],
        Intent.CALIBRATE_VOICE,
        0.96,
        None,
    ),
    (
        [
            "diagnose voice runtime",
            "voice runtime diagnostics",
            "why can't i hear you",
            "why cant i hear you",
        ],
        Intent.DIAGNOSE_VOICE_RUNTIME,
        0.96,
        None,
    ),
    (
        ["reset jarvis runtime", "reset voice runtime", "stay open", "don't close", "dont close"],
        Intent.RESET_JARVIS_RUNTIME,
        0.96,
        None,
    ),
    (
        [
            "show jarvis status",
            "how are you running",
            "what's your status",
            "whats your status",
            "what is your status",
        ],
        Intent.SHOW_JARVIS_STATUS,
        0.95,
        None,
    ),
    (
        ["show diagnostics", "show me diagnostics", "run diagnostics"],
        Intent.RUN_DIAGNOSTICS,
        0.94,
        None,
    ),
    (
        [
            "what am i doing",
            "what are you seeing",
            "current workspace",
        ],
        Intent.WHAT_AM_I_DOING,
        0.94,
        None,
    ),
    (
        [
            "what were we doing",
            "where were we",
            "what was i working on",
            "continue from yesterday",
            "open the thing we were working on",
        ],
        Intent.WHAT_WERE_WE_DOING,
        0.93,
        None,
    ),
    (
        ["summarize session", "session summary"],
        Intent.SUMMARIZE_SESSION,
        0.92,
        None,
    ),
    (
        [
            "open the dashboard",
            "show the dashboard",
            "go to dashboard",
        ],
        Intent.OPEN_TRADING_DASHBOARD,
        0.94,
        None,
    ),
    (
        [
            "describe screen",
            "what's on my screen",
            "whats on my screen",
            "what is on my screen",
        ],
        Intent.DESCRIBE_SCREEN,
        0.94,
        None,
    ),
    (
        ["analyze active window", "look at this window"],
        Intent.ANALYZE_ACTIVE_WINDOW,
        0.94,
        None,
    ),
    (
        ["show runtime status", "runtime status", "jarvis status"],
        Intent.SHOW_RUNTIME_STATUS,
        0.95,
        None,
    ),
    (
        ["show latency status", "latency status", "voice latency", "show voice latency budget"],
        Intent.SHOW_LATENCY_STATUS,
        0.95,
        None,
    ),
    (
        [
            "show voice performance status",
            "voice performance status",
            "voice performance",
        ],
        Intent.SHOW_VOICE_PERFORMANCE_STATUS,
        0.95,
        None,
    ),
    (
        ["list workflows", "show workflows"],
        Intent.LIST_WORKFLOWS,
        0.93,
        None,
    ),
    (
        ["run diagnostics", "run diagnostic"],
        Intent.RUN_DIAGNOSTICS,
        0.93,
        None,
    ),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().lower()
    return re.sub(r"\s+", " ", text)


_EXACT_ONLY_PHRASES = frozenset({"show dashboard"})


def _phrase_matches(normalized: str, phrase: str) -> bool:
    """Exact or prefix match — avoids 'show dashboard' matching 'show dashboard health'."""
    if normalized == phrase:
        return True
    if phrase in _EXACT_ONLY_PHRASES:
        return False
    return normalized.startswith(phrase + " ")


def match_english_voice_phrase(text: str) -> CommandRequest | None:
    """Return a high-confidence CommandRequest for known English voice phrases."""
    normalized = _normalize(text)
    if not normalized:
        return None

    best: CommandRequest | None = None
    for phrases, intent, confidence, params in _ENGLISH_VOICE_PHRASES:
        for phrase in phrases:
            p = _normalize(phrase)
            if _phrase_matches(normalized, p):
                if best is None or confidence > best.confidence:
                    best = CommandRequest(
                        raw_text=text,
                        intent=intent,
                        confidence=confidence,
                        params=dict(params) if params else {},
                        language="en",
                        classifier_source="rules",
                    )
                break
    return best


from core.intent_validation import assert_phrase_table_valid

assert_phrase_table_valid(_ENGLISH_VOICE_PHRASES, source="english_voice_phrases", expected_row_len=4)
