"""High-priority operational command classification (Phase 51)."""

from __future__ import annotations

import re
import unicodedata

from core.types import CommandRequest, Intent

_EXACT_PHRASES: dict[str, Intent] = {
    "phase 49 status": Intent.PHASE49_STATUS,
    "phase49 status": Intent.PHASE49_STATUS,
    "phase 50 status": Intent.PHASE50_STATUS,
    "phase50 status": Intent.PHASE50_STATUS,
    "phase 45 status": Intent.PHASE45_STATUS,
    "phase45 status": Intent.PHASE45_STATUS,
    "phase 46 status": Intent.PHASE46_STATUS,
    "phase46 status": Intent.PHASE46_STATUS,
    "what windows are open": Intent.SHOW_OPEN_WINDOWS,
    "list windows": Intent.SHOW_OPEN_WINDOWS,
    "show open windows": Intent.SHOW_OPEN_WINDOWS,
    "active windows": Intent.SHOW_OPEN_WINDOWS,
    "show screen system status": Intent.SHOW_SCREEN_SYSTEM_STATUS,
    "screen system status": Intent.SHOW_SCREEN_SYSTEM_STATUS,
    "show focused window": Intent.SHOW_FOCUSED_WINDOW,
    "switch to browser": Intent.SWITCH_TO_BROWSER,
    "focus browser": Intent.SWITCH_TO_BROWSER,
    "switch to cursor": Intent.SWITCH_TO_CURSOR,
    "switch to dashboard": Intent.SWITCH_TO_DASHBOARD,
    "focus terminal": Intent.FOCUS_TERMINAL,
    "show memory state": Intent.SHOW_MEMORY_STATE,
    "clear completed task": Intent.CLEAR_COMPLETED_TASK,
    "pin investigation": Intent.PIN_INVESTIGATION,
    "continue trading investigation": Intent.CONTINUE_TRADING_INVESTIGATION,
    "show trading operations dashboard": Intent.SHOW_TRADING_OPERATIONS_DASHBOARD,
    "trading operations dashboard": Intent.SHOW_TRADING_OPERATIONS_DASHBOARD,
    "show running tasks": Intent.SHOW_RUNNING_TASKS,
    "running tasks": Intent.SHOW_RUNNING_TASKS,
    "show completed tasks": Intent.SHOW_COMPLETED_TASKS,
    "completed tasks": Intent.SHOW_COMPLETED_TASKS,
    "show failed tasks": Intent.SHOW_FAILED_TASKS,
    "failed tasks": Intent.SHOW_FAILED_TASKS,
    "rerun last task": Intent.RERUN_LAST_BACKGROUND_TASK,
    "show recent results": Intent.SHOW_RECENT_RESULTS,
    "recent results": Intent.SHOW_RECENT_RESULTS,
    "show notifications": Intent.SHOW_NOTIFICATIONS,
    "notifications": Intent.SHOW_NOTIFICATIONS,
    "clear notifications": Intent.CLEAR_NOTIFICATIONS,
    "explain last result": Intent.EXPLAIN_LAST_RESULT,
    "continue previous session": Intent.CONTINUE_PREVIOUS_SESSION,
    "summarize unresolved issues": Intent.SUMMARIZE_UNRESOLVED_ISSUES,
    "resume latest investigation": Intent.RESUME_LATEST_INVESTIGATION,
    "what changed since last session": Intent.WHAT_CHANGED_SINCE_LAST_SESSION,
    "summarize system intelligence": Intent.SUMMARIZE_SYSTEM_INTELLIGENCE,
    "summarize unresolved blockers": Intent.SUMMARIZE_UNRESOLVED_BLOCKERS,
    "explain current operational state": Intent.EXPLAIN_CURRENT_OPERATIONAL_STATE,
    "recommend next action": Intent.RECOMMEND_NEXT_ACTION,
    "what should we investigate next": Intent.WHAT_SHOULD_WE_INVESTIGATE_NEXT,
    "show investigation schedule": Intent.SHOW_INVESTIGATION_SCHEDULE,
    "run investigation cycle": Intent.RUN_INVESTIGATION_CYCLE,
    "pause investigation loop": Intent.PAUSE_INVESTIGATION_LOOP,
    "resume investigation loop": Intent.RESUME_INVESTIGATION_LOOP,
    "run nightly investigation now": Intent.RUN_NIGHTLY_INVESTIGATION_NOW,
    "show blocker trends": Intent.SHOW_BLOCKER_TRENDS,
    "compare blocker trends": Intent.COMPARE_BLOCKER_TRENDS,
    "explain dominant blocker": Intent.EXPLAIN_DOMINANT_BLOCKER,
    "show blocker history": Intent.SHOW_BLOCKER_HISTORY,
    "cluster replay divergences": Intent.CLUSTER_REPLAY_DIVERGENCES,
    "show divergence clusters": Intent.SHOW_DIVERGENCE_CLUSTERS,
    "explain largest divergence cluster": Intent.EXPLAIN_LARGEST_DIVERGENCE_CLUSTER,
    "show active hypotheses": Intent.SHOW_ACTIVE_HYPOTHESES,
    "verify active hypotheses": Intent.VERIFY_ACTIVE_HYPOTHESES,
    "explain top hypothesis": Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS,
    "compare hypothesis history": Intent.COMPARE_HYPOTHESIS_HISTORY,
    "show intelligence timeline": Intent.SHOW_INTELLIGENCE_TIMELINE,
    "explain recent anomalies": Intent.EXPLAIN_RECENT_ANOMALIES,
    "compare today vs yesterday intelligence": Intent.COMPARE_TODAY_VS_YESTERDAY_INTELLIGENCE,
    "summarize autonomous findings": Intent.SUMMARIZE_AUTONOMOUS_FINDINGS,
    "summarize operational anomalies": Intent.SUMMARIZE_OPERATIONAL_ANOMALIES,
    "explain current trading risk": Intent.EXPLAIN_CURRENT_TRADING_RISK,
    "show verification plans": Intent.SHOW_VERIFICATION_PLANS,
    "explain verification plan": Intent.EXPLAIN_VERIFICATION_PLAN,
    "run verification plan": Intent.RUN_VERIFICATION_PLAN,
    "verify root causes": Intent.VERIFY_ROOT_CAUSES,
    "show confidence evolution": Intent.SHOW_CONFIDENCE_EVOLUTION,
    "explain confidence changes": Intent.EXPLAIN_CONFIDENCE_CHANGES,
    "compare root cause confidence": Intent.COMPARE_ROOT_CAUSE_CONFIDENCE,
    "show contradictory evidence": Intent.SHOW_CONTRADICTORY_EVIDENCE,
    "explain contradiction": Intent.EXPLAIN_CONTRADICTION,
    "resolve contradiction": Intent.RESOLVE_CONTRADICTION,
    "suggest experiments": Intent.SUGGEST_EXPERIMENTS,
    "explain experiment impact": Intent.EXPLAIN_EXPERIMENT_IMPACT,
    "run safe experiment simulation": Intent.RUN_SAFE_EXPERIMENT_SIMULATION,
    "show root cause graph": Intent.SHOW_ROOT_CAUSE_GRAPH,
    "explain root cause graph": Intent.EXPLAIN_ROOT_CAUSE_GRAPH,
    "trace causal chain": Intent.TRACE_CAUSAL_CHAIN,
    "summarize root causes": Intent.SUMMARIZE_ROOT_CAUSES,
    "explain dominant root cause": Intent.EXPLAIN_DOMINANT_ROOT_CAUSE,
    "explain operational failures": Intent.EXPLAIN_OPERATIONAL_FAILURES,
    "summarize verified findings": Intent.SUMMARIZE_VERIFIED_FINDINGS,
    "explain why trades are blocked": Intent.EXPLAIN_WHY_TRADES_ARE_BLOCKED,
    "compare operational periods": Intent.COMPARE_OPERATIONAL_PERIODS,
    "compare before after cleanup": Intent.COMPARE_BEFORE_AFTER_CLEANUP,
    "compare investigation periods": Intent.COMPARE_INVESTIGATION_PERIODS,
    "what are we discussing": Intent.WHAT_ARE_WE_DISCUSSING,
    "summarize current conversation": Intent.SUMMARIZE_CURRENT_CONVERSATION,
    "resume previous topic": Intent.RESUME_PREVIOUS_TOPIC,
    "show conversation state": Intent.SHOW_CONVERSATION_STATE,
    "start continuous listening": Intent.START_CONTINUOUS_LISTENING,
    "stop continuous listening": Intent.STOP_CONTINUOUS_LISTENING,
    "explain this project": Intent.EXPLAIN_THIS_PROJECT,
    "prepare investor summary": Intent.PREPARE_INVESTOR_SUMMARY,
    "explain architecture": Intent.EXPLAIN_ARCHITECTURE,
    "generate project roadmap": Intent.GENERATE_PROJECT_ROADMAP,
    "show project intelligence": Intent.SHOW_PROJECT_INTELLIGENCE,
    "propose engineering patch": Intent.PROPOSE_ENGINEERING_PATCH,
    "simulate engineering patch": Intent.SIMULATE_ENGINEERING_PATCH,
    "validate engineering patch": Intent.VALIDATE_ENGINEERING_PATCH,
    "explain patch risks": Intent.EXPLAIN_PATCH_RISKS,
    "show proactive suggestions": Intent.SHOW_PROACTIVE_SUGGESTIONS,
    "show realtime runtime": Intent.SHOW_REALTIME_RUNTIME,
    "phase 56 status": Intent.PHASE56_STATUS,
    "phase56 status": Intent.PHASE56_STATUS,
    "show voice latency": Intent.SHOW_VOICE_LATENCY,
    "phase 57 status": Intent.PHASE57_STATUS,
    "phase57 status": Intent.PHASE57_STATUS,
    "test realtime voice": Intent.TEST_REALTIME_VOICE,
    "test interrupt speech": Intent.TEST_INTERRUPT_SPEECH,
    "show realtime provider status": Intent.SHOW_REALTIME_PROVIDER_STATUS,
    "benchmark realtime providers": Intent.BENCHMARK_REALTIME_PROVIDERS,
    "show realtime latency breakdown": Intent.SHOW_REALTIME_LATENCY_BREAKDOWN,
    "test websocket realtime voice": Intent.TEST_WEBSOCKET_REALTIME_VOICE,
    "benchmark realtime streaming": Intent.BENCHMARK_REALTIME_STREAMING,
    "show runtime config sources": Intent.SHOW_RUNTIME_CONFIG_SOURCES,
    "show runtime config mismatches": Intent.SHOW_RUNTIME_CONFIG_MISMATCHES,
    "show capability health": Intent.SHOW_CAPABILITY_HEALTH,
    "show voice health": Intent.SHOW_VOICE_HEALTH,
    "repair memory store": Intent.REPAIR_MEMORY_STORE,
    "show browser health": Intent.SHOW_BROWSER_HEALTH,
    "show desktop operator health": Intent.SHOW_DESKTOP_OPERATOR_HEALTH,
    "show system health": Intent.SHOW_SYSTEM_HEALTH,
    "show performance report": Intent.SHOW_PERFORMANCE_REPORT,
    "summarize my inbox": Intent.SUMMARIZE_MY_INBOX,
    "show urgent emails": Intent.SHOW_URGENT_EMAILS,
    "summarize my calendar": Intent.SUMMARIZE_MY_CALENDAR,
    "show memory debug": Intent.SHOW_MEMORY_DEBUG,
    "show browser debug": Intent.SHOW_BROWSER_DEBUG,
    "what is on my screen": Intent.WHAT_IS_ON_MY_SCREEN,
    "summarize this screen": Intent.SUMMARIZE_THIS_SCREEN,
    "click the button that says": Intent.CLICK_BUTTON_THAT_SAYS,
    "type this": Intent.TYPE_THIS,
    "switch to chrome": Intent.SWITCH_TO_CHROME,
    "list open windows": Intent.LIST_OPEN_WINDOWS,
    "open browser": Intent.OPEN_BROWSER,
    "find information about": Intent.FIND_INFORMATION_ABOUT,
    "open the best result": Intent.OPEN_BEST_RESULT,
    "summarize the top results": Intent.SUMMARIZE_TOP_RESULTS,
    "compare these search results": Intent.COMPARE_THESE_SEARCH_RESULTS,
    "extract key facts from this page": Intent.EXTRACT_KEY_FACTS_FROM_THIS_PAGE,
    "save browser research report": Intent.SAVE_BROWSER_RESEARCH_REPORT,
    "open website": Intent.OPEN_WEBSITE,
    "go to": Intent.OPEN_WEBSITE,
    "navigate to": Intent.OPEN_WEBSITE,
    "browse to": Intent.OPEN_WEBSITE,
    "test real browser": Intent.TEST_REAL_BROWSER,
    "test real voice conversation": Intent.TEST_REAL_VOICE_CONVERSATION,
    "show desktop vision health": Intent.SHOW_DESKTOP_VISION_HEALTH,
    "alpha setup check": Intent.ALPHA_SETUP_CHECK,
    "show alpha report": Intent.SHOW_ALPHA_REPORT,
    "summarize my day": Intent.SUMMARIZE_MY_DAY,
    "compare these pages": Intent.COMPARE_THESE_PAGES,
    "what tab is active": Intent.WHAT_TAB_IS_ACTIVE,
    "what page am i on": Intent.WHAT_TAB_IS_ACTIVE,
    "summarize current page": Intent.SUMMARIZE_THIS_PAGE,
    "summarize my last 100 emails": Intent.SUMMARIZE_MY_LAST_100_EMAILS,
    "what needs my attention today": Intent.WHAT_NEEDS_MY_ATTENTION_TODAY,
    "find calendar conflicts": Intent.FIND_CALENDAR_CONFLICTS,
    "summarize this page": Intent.SUMMARIZE_THIS_PAGE,
    "compare these results": Intent.COMPARE_THESE_RESULTS,
    "show tts debug": Intent.SHOW_TTS_DEBUG,
    "test tts playback": Intent.TEST_TTS_PLAYBACK,
    "test direct tts": Intent.TEST_DIRECT_TTS,
    "test streaming stt": Intent.TEST_STREAMING_STT,
    "show conversation runtime": Intent.SHOW_CONVERSATION_RUNTIME,
    "show interruption metrics": Intent.SHOW_INTERRUPTION_METRICS,
    "show conversational memory": Intent.SHOW_CONVERSATIONAL_MEMORY,
    "benchmark full duplex conversation": Intent.BENCHMARK_FULL_DUPLEX_CONVERSATION,
    "phase 59 status": Intent.PHASE59_STATUS,
    "phase59 status": Intent.PHASE59_STATUS,
    "cancel active speech": Intent.CANCEL_ACTIVE_SPEECH,
}

_REOPEN_TASK_RE = re.compile(r"^reopen task result\s+(\d+)$")
_ARCHIVE_NOTIFICATION_RE = re.compile(r"^archive notification\s+(\d+)$")
_EXPLAIN_NOTIFICATION_RE = re.compile(r"^explain notification\s+(\d+)$")
_CANCEL_TASK_RE = re.compile(r"^cancel task\s+(\d+)$")


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "").strip().lower()
    value = re.sub(r"[.!?,;:]+$", "", value).strip()
    return re.sub(r"\s+", " ", value)


def _prepare_text(text: str) -> str:
    try:
        from voice.command_input import prepare_command_text

        return prepare_command_text(text)
    except Exception:
        return text.strip()


def match_operational_priority_commands(text: str) -> CommandRequest | None:
    """Exact operational phrases before fuzzy phase/grammar matchers."""
    prepared = _prepare_text(text)
    normalized = _normalize(prepared)
    if not normalized:
        return None

    intent = _EXACT_PHRASES.get(normalized)
    if intent is None:
        for pattern, target_intent, param_key in (
            (_CANCEL_TASK_RE, Intent.CANCEL_TASK, "task_id"),
            (_REOPEN_TASK_RE, Intent.REOPEN_TASK_RESULT, "task_id"),
            (_ARCHIVE_NOTIFICATION_RE, Intent.ARCHIVE_NOTIFICATION, "notification_id"),
            (_EXPLAIN_NOTIFICATION_RE, Intent.EXPLAIN_NOTIFICATION, "notification_id"),
        ):
            match = pattern.match(normalized)
            if match:
                return CommandRequest(
                    raw_text=text,
                    intent=target_intent,
                    confidence=0.99,
                    params={param_key: int(match.group(1))},
                    classifier_source="operational_phrases",
                )
    if intent is None and normalized.startswith("search reports"):
        return CommandRequest(
            raw_text=text,
            intent=Intent.SEARCH_REPORTS,
            confidence=0.98,
            params={"query": normalized.replace("search reports", "", 1).strip()},
            classifier_source="operational_phrases",
        )
    if intent is None:
        return None

    params: dict[str, object] = {}
    if intent == Intent.PIN_INVESTIGATION and "pin investigation" in normalized:
        tail = normalized.replace("pin investigation", "", 1).strip()
        if tail:
            params["title"] = tail

    return CommandRequest(
        raw_text=text,
        intent=intent,
        confidence=0.99,
        params=params,
        classifier_source="operational_phrases",
    )


def validate_operational_phrase_collisions() -> list[str]:
    """Ensure phase 49/50 never map to phase45 via substring rules."""
    issues: list[str] = []
    for phrase, expected in (
        ("phase 49 status", Intent.PHASE49_STATUS),
        ("phase 50 status", Intent.PHASE50_STATUS),
    ):
        req = match_operational_priority_commands(phrase)
        if req is None:
            issues.append(f"operational phrase {phrase!r} has no matcher")
        elif req.intent != expected:
            issues.append(f"operational phrase {phrase!r} maps to {req.intent.value}, expected {expected.value}")
        elif req.intent == Intent.PHASE45_STATUS:
            issues.append(f"operational phrase {phrase!r} incorrectly maps to phase45_status")
    return issues
