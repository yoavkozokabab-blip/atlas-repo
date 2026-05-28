"""Intent registry consistency checks across classifier and action wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.types import Intent

# Phase 46.3–46.5 intents that must exist on Intent before phrase modules load.
REQUIRED_PHASE_INTENT_MEMBERS: tuple[str, ...] = (
    "RUN_HISTORICAL_VALIDATION_SWEEP",
    "SHOW_VALIDATION_SWEEP",
    "EXPORT_VALIDATION_SWEEP",
    "COMPARE_STRATEGY_METRICS_BEFORE_AFTER",
    "SHOW_WORST_DIVERGENCE_SYMBOLS",
    "ESTIMATE_PRODUCTION_RISK",
    "RECOMMEND_PRODUCTION_ACTION",
    "SHOW_INVESTIGATION_SUMMARY",
    "AUDIT_PRICE_INTEGRITY",
    "COMPARE_CANDLE_SOURCES",
    "TRACE_PRICE_SOURCE",
    "FIND_CLOSE_PRICE_MISMATCHES",
    "INSPECT_DATA_CACHE_DRIFT",
    "CHECK_TIMESTAMP_ALIGNMENT",
    "CHECK_ADJUSTED_PRICE_USAGE",
    "CHECK_DUPLICATE_BARS",
    "GENERATE_PRICE_INTEGRITY_REPORT",
    "AUDIT_EXECUTION_PATH",
    "EXPLAIN_ZERO_EXECUTION_ATTEMPTS",
    "TRACE_SIGNAL_TO_ORDER",
    "SHOW_EXECUTION_BLOCKERS",
    "RANK_EXECUTION_BLOCK_REASONS",
    "INSPECT_EXECUTION_ADAPTER",
    "COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS",
    "GENERATE_EXECUTION_INVESTIGATION_REPORT",
    "TRACE_SIGNAL_TO_EXECUTION",
    "TRACE_BLOCKED_SIGNAL",
    "EXPLAIN_TOP_EXECUTION_BLOCKER",
    "RECONSTRUCT_EXECUTION_FLOW",
    "SHOW_SIGNAL_LIFECYCLE_TIMELINE",
    "RANK_DEAD_SIGNAL_CAUSES",
    "SIMULATE_UNBLOCK_SCENARIO",
    "PROPOSE_EXECUTION_FIX",
    "GENERATE_EXECUTION_FLOW_REPORT",
    "SIMULATE_EXECUTION_CLEANUP_PATCH",
    "COMPARE_RISK_BEFORE_AFTER_CLEANUP",
    "SHOW_STALE_OPEN_POSITIONS",
    "PROPOSE_EXECUTION_CLEANUP_PATCH",
    "GENERATE_EXECUTION_CLEANUP_REPORT",
    "SHOW_APPROVED_PATCH",
    "VALIDATE_PATCH_SAFETY",
    "APPLY_APPROVED_PATCH",
    "ROLLBACK_LAST_PATCH",
    "SHOW_PATCH_HISTORY",
    "VALIDATE_APPLIED_PATCH",
    "REPLAY_AFTER_PATCH",
    "COMPARE_PRE_POST_PATCH",
    "RUN_PATCH_WORKFLOW",
    "SHOW_PATCH_WORKFLOW_STATUS",
    "SHOW_RUNTIME_HEALTH",
    "SHOW_HEALING_ACTIONS",
    "SHOW_STUCK_WORKERS",
    "RESTART_FAILED_WORKER",
    "CLEAR_STALE_LOCKS",
    "RECOVER_OVERLAY",
    "RECOVER_VOICE_SYSTEM",
    "RESTART_DASHBOARD",
    "RESTART_WAKE_LISTENER",
    "RESTART_OPERATOR_CONSOLE",
    "VALIDATE_RUNTIME_INTEGRITY",
    "PHASE49_STATUS",
    "WHAT_AM_I_LOOKING_AT",
    "SUMMARIZE_CURRENT_SCREEN",
    "SUMMARIZE_TRADING_HEALTH",
    "EXPLAIN_WHY_NO_TRADES_TODAY",
    "COMPARE_TODAY_VS_YESTERDAY",
    "SHOW_TOP_OPERATIONAL_BLOCKERS",
    "SHOW_CURRENT_EXECUTION_RISK",
    "SUMMARIZE_LIVE_ENGINE_STATUS",
    "RESUME_LAST_TASK",
    "SHOW_RECENT_INVESTIGATIONS",
    "CONTINUE_INVESTIGATION",
    "OPEN_LAST_REPORT",
    "SEARCH_REPORTS",
    "SHOW_CURRENT_STATE",
    "SHOW_ACTIVE_SYSTEMS",
    "SHOW_RUNTIME_SUMMARY",
    "SHOW_OPERATIONAL_SUGGESTIONS",
    "PHASE50_STATUS",
    "SHOW_OPEN_WINDOWS",
    "SHOW_SCREEN_SYSTEM_STATUS",
    "SHOW_FOCUSED_WINDOW",
    "SWITCH_TO_BROWSER",
    "SWITCH_TO_CURSOR",
    "SWITCH_TO_DASHBOARD",
    "FOCUS_TERMINAL",
    "SHOW_MEMORY_STATE",
    "CLEAR_COMPLETED_TASK",
    "PIN_INVESTIGATION",
    "CONTINUE_TRADING_INVESTIGATION",
    "SHOW_TRADING_OPERATIONS_DASHBOARD",
    "SHOW_RUNNING_TASKS",
    "CANCEL_TASK",
    "SHOW_COMPLETED_TASKS",
    "SHOW_FAILED_TASKS",
    "RERUN_LAST_BACKGROUND_TASK",
    "SHOW_RECENT_RESULTS",
    "SHOW_NOTIFICATIONS",
    "CLEAR_NOTIFICATIONS",
    "EXPLAIN_LAST_RESULT",
    "REOPEN_TASK_RESULT",
    "ARCHIVE_NOTIFICATION",
    "EXPLAIN_NOTIFICATION",
    "CONTINUE_PREVIOUS_SESSION",
    "SUMMARIZE_UNRESOLVED_ISSUES",
    "RESUME_LATEST_INVESTIGATION",
    "WHAT_CHANGED_SINCE_LAST_SESSION",
    "SUMMARIZE_SYSTEM_INTELLIGENCE",
    "SUMMARIZE_UNRESOLVED_BLOCKERS",
    "EXPLAIN_CURRENT_OPERATIONAL_STATE",
    "RECOMMEND_NEXT_ACTION",
    "WHAT_SHOULD_WE_INVESTIGATE_NEXT",
    "SHOW_INVESTIGATION_SCHEDULE",
    "RUN_INVESTIGATION_CYCLE",
    "PAUSE_INVESTIGATION_LOOP",
    "RESUME_INVESTIGATION_LOOP",
    "RUN_NIGHTLY_INVESTIGATION_NOW",
    "SHOW_BLOCKER_TRENDS",
    "COMPARE_BLOCKER_TRENDS",
    "EXPLAIN_DOMINANT_BLOCKER",
    "SHOW_BLOCKER_HISTORY",
    "CLUSTER_REPLAY_DIVERGENCES",
    "SHOW_DIVERGENCE_CLUSTERS",
    "EXPLAIN_LARGEST_DIVERGENCE_CLUSTER",
    "SHOW_ACTIVE_HYPOTHESES",
    "VERIFY_ACTIVE_HYPOTHESES",
    "EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS",
    "COMPARE_HYPOTHESIS_HISTORY",
    "SHOW_INTELLIGENCE_TIMELINE",
    "EXPLAIN_RECENT_ANOMALIES",
    "COMPARE_TODAY_VS_YESTERDAY_INTELLIGENCE",
    "SUMMARIZE_AUTONOMOUS_FINDINGS",
    "SUMMARIZE_OPERATIONAL_ANOMALIES",
    "EXPLAIN_CURRENT_TRADING_RISK",
    "SHOW_VERIFICATION_PLANS",
    "EXPLAIN_VERIFICATION_PLAN",
    "RUN_VERIFICATION_PLAN",
    "VERIFY_ROOT_CAUSES",
    "SHOW_CONFIDENCE_EVOLUTION",
    "EXPLAIN_CONFIDENCE_CHANGES",
    "COMPARE_ROOT_CAUSE_CONFIDENCE",
    "SHOW_CONTRADICTORY_EVIDENCE",
    "EXPLAIN_CONTRADICTION",
    "RESOLVE_CONTRADICTION",
    "SUGGEST_EXPERIMENTS",
    "EXPLAIN_EXPERIMENT_IMPACT",
    "RUN_SAFE_EXPERIMENT_SIMULATION",
    "SHOW_ROOT_CAUSE_GRAPH",
    "EXPLAIN_ROOT_CAUSE_GRAPH",
    "TRACE_CAUSAL_CHAIN",
    "SUMMARIZE_ROOT_CAUSES",
    "EXPLAIN_DOMINANT_ROOT_CAUSE",
    "EXPLAIN_OPERATIONAL_FAILURES",
    "SUMMARIZE_VERIFIED_FINDINGS",
    "EXPLAIN_WHY_TRADES_ARE_BLOCKED",
    "COMPARE_OPERATIONAL_PERIODS",
    "COMPARE_BEFORE_AFTER_CLEANUP",
    "COMPARE_INVESTIGATION_PERIODS",
    "WHAT_ARE_WE_DISCUSSING",
    "SUMMARIZE_CURRENT_CONVERSATION",
    "RESUME_PREVIOUS_TOPIC",
    "SHOW_CONVERSATION_STATE",
    "START_CONTINUOUS_LISTENING",
    "STOP_CONTINUOUS_LISTENING",
    "EXPLAIN_THIS_PROJECT",
    "PREPARE_INVESTOR_SUMMARY",
    "EXPLAIN_ARCHITECTURE",
    "GENERATE_PROJECT_ROADMAP",
    "SHOW_PROJECT_INTELLIGENCE",
    "PROPOSE_ENGINEERING_PATCH",
    "SIMULATE_ENGINEERING_PATCH",
    "VALIDATE_ENGINEERING_PATCH",
    "EXPLAIN_PATCH_RISKS",
    "SHOW_PROACTIVE_SUGGESTIONS",
    "SHOW_REALTIME_RUNTIME",
    "PHASE56_STATUS",
)

PHASE55_INTENT_MEMBERS: tuple[str, ...] = (
    "SUMMARIZE_ROOT_CAUSES",
    "EXPLAIN_DOMINANT_ROOT_CAUSE",
    "VERIFY_ROOT_CAUSES",
    "SHOW_VERIFICATION_PLANS",
    "EXPLAIN_VERIFICATION_PLAN",
    "RUN_VERIFICATION_PLAN",
    "SHOW_CONFIDENCE_EVOLUTION",
    "EXPLAIN_CONFIDENCE_CHANGES",
    "COMPARE_ROOT_CAUSE_CONFIDENCE",
    "SHOW_CONTRADICTORY_EVIDENCE",
    "EXPLAIN_CONTRADICTION",
    "RESOLVE_CONTRADICTION",
    "SUGGEST_EXPERIMENTS",
    "EXPLAIN_EXPERIMENT_IMPACT",
    "RUN_SAFE_EXPERIMENT_SIMULATION",
    "SHOW_ROOT_CAUSE_GRAPH",
    "EXPLAIN_ROOT_CAUSE_GRAPH",
    "TRACE_CAUSAL_CHAIN",
    "EXPLAIN_OPERATIONAL_FAILURES",
    "SUMMARIZE_VERIFIED_FINDINGS",
    "EXPLAIN_WHY_TRADES_ARE_BLOCKED",
    "COMPARE_OPERATIONAL_PERIODS",
    "COMPARE_BEFORE_AFTER_CLEANUP",
    "COMPARE_INVESTIGATION_PERIODS",
)

PHASE55_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in PHASE55_INTENT_MEMBERS if hasattr(Intent, member)
)

PHASE56_INTENT_MEMBERS: tuple[str, ...] = (
    "WHAT_ARE_WE_DISCUSSING",
    "SUMMARIZE_CURRENT_CONVERSATION",
    "RESUME_PREVIOUS_TOPIC",
    "SHOW_CONVERSATION_STATE",
    "START_CONTINUOUS_LISTENING",
    "STOP_CONTINUOUS_LISTENING",
    "EXPLAIN_THIS_PROJECT",
    "PREPARE_INVESTOR_SUMMARY",
    "EXPLAIN_ARCHITECTURE",
    "GENERATE_PROJECT_ROADMAP",
    "SHOW_PROJECT_INTELLIGENCE",
    "PROPOSE_ENGINEERING_PATCH",
    "SIMULATE_ENGINEERING_PATCH",
    "VALIDATE_ENGINEERING_PATCH",
    "EXPLAIN_PATCH_RISKS",
    "SHOW_PROACTIVE_SUGGESTIONS",
    "SHOW_REALTIME_RUNTIME",
    "PHASE56_STATUS",
)

PHASE56_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in PHASE56_INTENT_MEMBERS if hasattr(Intent, member)
)

PHASE57_INTENT_MEMBERS: tuple[str, ...] = (
    "SHOW_VOICE_LATENCY",
    "PHASE57_STATUS",
    "TEST_REALTIME_VOICE",
    "TEST_INTERRUPT_SPEECH",
    "SHOW_REALTIME_PROVIDER_STATUS",
    "BENCHMARK_REALTIME_PROVIDERS",
    "CANCEL_ACTIVE_SPEECH",
)

PHASE57_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in PHASE57_INTENT_MEMBERS if hasattr(Intent, member)
)

# Implemented via ActionRegistry.execute inline branch, not a registered Action class.
REGISTRY_INLINE_INTENTS: frozenset[str] = frozenset({"shutdown_jarvis"})

REQUIRED_PHASE_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in REQUIRED_PHASE_INTENT_MEMBERS if hasattr(Intent, member)
)


@dataclass(frozen=True)
class IntentValidationIssue:
    category: str
    message: str

    def format(self) -> str:
        return f"[{self.category}] {self.message}"


def _intent_values(table: Iterable[Any], intent_index: int) -> list[Intent]:
    values: list[Intent] = []
    for row in table:
        intent: Any | None = None
        if hasattr(row, "intent"):
            intent = getattr(row, "intent")
        elif isinstance(row, tuple) and len(row) > intent_index:
            intent = row[intent_index]
        if isinstance(intent, Intent):
            values.append(intent)
    return values


def validate_required_intent_enums() -> list[IntentValidationIssue]:
    issues: list[IntentValidationIssue] = []
    for member in REQUIRED_PHASE_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(
                IntentValidationIssue(
                    "intent_enum",
                    f"Intent enum missing member {member}",
                )
            )
    return issues


def assert_phrase_table_valid(
    table: Iterable[tuple[Any, ...]],
    *,
    source: str,
    intent_index: int = 1,
    expected_row_len: int | None = None,
) -> None:
    """Validate a phrase table at import time; raise ImportError on inconsistency."""
    issues = validate_phrase_table(table, source=source, intent_index=intent_index)
    if expected_row_len is not None:
        issues.extend(
            validate_phrase_table_row_lengths(
                table,
                source=source,
                expected_len=expected_row_len,
            )
        )
    if issues:
        lines = "\n".join(i.format() for i in issues)
        raise ImportError(f"{source} intent validation failed:\n{lines}")


def validate_phrase_table_row_lengths(
    table: Iterable[tuple[Any, ...]],
    *,
    source: str,
    expected_len: int,
) -> list[IntentValidationIssue]:
    """Ensure tuple phrase rows match unpack arity (e.g. phrases, intent, confidence)."""
    issues: list[IntentValidationIssue] = []
    for idx, row in enumerate(table):
        if not isinstance(row, tuple):
            continue
        if len(row) != expected_len:
            intent_hint = row[1] if len(row) > 1 else "?"
            issues.append(
                IntentValidationIssue(
                    source,
                    f"row {idx} len={len(row)} expected {expected_len} (intent={intent_hint!r})",
                )
            )
    return issues


def validate_phrase_table(
    table: Iterable[tuple[Any, ...]],
    *,
    source: str,
    intent_index: int = 1,
) -> list[IntentValidationIssue]:
    from config import ALLOWED_INTENTS

    issues: list[IntentValidationIssue] = []
    for intent in _intent_values(table, intent_index):
        if intent.value not in ALLOWED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    source,
                    f"{intent.name} ({intent.value}) not in ALLOWED_INTENTS",
                )
            )
    return issues


def _collect_phrase_sources() -> list[tuple[str, Iterable[tuple[Any, ...]], int]]:
    from brain.command_grammar import _COMMAND_GRAMMAR
    from brain.english_voice_phrases import _ENGLISH_VOICE_PHRASES
    from brain.instant_fast_lane import _FAST_LANE_PHRASES
    from brain.intent_classifier import _PHRASE_RULES

    return [
        ("english_voice_phrases", _ENGLISH_VOICE_PHRASES, 1),
        ("intent_classifier", _PHRASE_RULES, 1),
        ("command_grammar", _COMMAND_GRAMMAR, 1),
        ("instant_fast_lane", _FAST_LANE_PHRASES, 1),
    ]


def validate_intent_registry_consistency(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    """
    Verify phrase tables, Intent enum, ALLOWED_INTENTS, IMPLEMENTED_INTENTS, and registry actions.
    Returns issue objects; empty list means consistent.
    """
    from config import ALLOWED_INTENTS, IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    issues.extend(validate_required_intent_enums())

    referenced: set[str] = set()
    row_len_by_source = {
        "english_voice_phrases": 4,
        "intent_classifier": 3,
    }
    for source, table, intent_index in _collect_phrase_sources():
        for row_issue in validate_phrase_table(table, source=source, intent_index=intent_index):
            issues.append(row_issue)
        expected_len = row_len_by_source.get(source)
        if expected_len is not None:
            for row_issue in validate_phrase_table_row_lengths(
                table,
                source=source,
                expected_len=expected_len,
            ):
                issues.append(row_issue)
        for intent in _intent_values(table, intent_index):
            referenced.add(intent.value)

    for value in sorted(referenced):
        if value not in ALLOWED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "allowed_intents",
                    f"Referenced intent {value!r} missing from ALLOWED_INTENTS",
                )
            )

    if check_registry:
        try:
            from actions.registry import ActionRegistry

            registry = ActionRegistry()
            registered = set(registry._actions.keys())
        except Exception as exc:
            issues.append(
                IntentValidationIssue(
                    "registry",
                    f"ActionRegistry failed to load: {type(exc).__name__}: {exc}",
                )
            )
            registered = set()

        for value in sorted(IMPLEMENTED_INTENTS):
            if value in {"unknown", "clarify"} or value in REGISTRY_INLINE_INTENTS:
                continue
            if value not in registered:
                issues.append(
                    IntentValidationIssue(
                        "registry",
                        f"IMPLEMENTED_INTENTS includes {value!r} but no Action is registered",
                    )
                )

        for value in sorted(referenced):
            if value in IMPLEMENTED_INTENTS and value not in registered and value not in REGISTRY_INLINE_INTENTS:
                issues.append(
                    IntentValidationIssue(
                        "registry",
                        f"Phrase maps to implemented intent {value!r} but registry has no handler",
                    )
                )

        for member in REQUIRED_PHASE_INTENT_MEMBERS:
            if not hasattr(Intent, member):
                continue
            value = getattr(Intent, member).value
            if value in IMPLEMENTED_INTENTS and value not in registered:
                issues.append(
                    IntentValidationIssue(
                        "registry",
                        f"Required phase intent {member} ({value!r}) has no registered Action",
                    )
                )

    return issues


def validate_patch_workflow_phrase_collisions() -> list[IntentValidationIssue]:
    """Ensure patch workflow phrases never classify as generic run_workflow."""
    from brain.patch_command_phrases import validate_patch_workflow_phrase_collisions as _validate

    return [
        IntentValidationIssue("patch_workflow", message)
        for message in _validate()
    ]


def validate_phase55_runtime_wiring(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    """Verify Phase 55 intents are implemented and registered for runtime execution."""
    from config import IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    for member in PHASE55_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(
                IntentValidationIssue(
                    "phase55",
                    f"Intent enum missing Phase 55 member {member}",
                )
            )
            continue
        value = getattr(Intent, member).value
        if value not in IMPLEMENTED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "phase55",
                    f"Phase 55 intent {member} ({value!r}) missing from IMPLEMENTED_INTENTS",
                )
            )

    if not check_registry:
        return issues

    try:
        from actions.registry import ActionRegistry

        registry = ActionRegistry()
        registered = set(registry._actions.keys())
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase55",
                f"Phase 55 registry load failed: {type(exc).__name__}: {exc}",
            )
        )
        return issues

    try:
        import actions.phase55_actions  # noqa: F401
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase55",
                f"actions.phase55_actions import failed: {type(exc).__name__}: {exc}",
            )
        )

    for member in PHASE55_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            continue
        value = getattr(Intent, member).value
        if value in IMPLEMENTED_INTENTS and value not in registered:
            issues.append(
                IntentValidationIssue(
                    "phase55",
                    f"Phase 55 intent {member} ({value!r}) has no registered Action",
                )
            )

    return issues


def validate_phase56_runtime_wiring(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    """Verify Phase 56 intents are implemented and registered for runtime execution."""
    from config import IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    for member in PHASE56_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(
                IntentValidationIssue(
                    "phase56",
                    f"Intent enum missing Phase 56 member {member}",
                )
            )
            continue
        value = getattr(Intent, member).value
        if value not in IMPLEMENTED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "phase56",
                    f"Phase 56 intent {member} ({value!r}) missing from IMPLEMENTED_INTENTS",
                )
            )

    if not check_registry:
        return issues

    try:
        from actions.registry import ActionRegistry

        registry = ActionRegistry()
        registered = set(registry._actions.keys())
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase56",
                f"Phase 56 registry load failed: {type(exc).__name__}: {exc}",
            )
        )
        return issues

    try:
        import actions.phase56_actions  # noqa: F401
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase56",
                f"actions.phase56_actions import failed: {type(exc).__name__}: {exc}",
            )
        )

    for member in PHASE56_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            continue
        value = getattr(Intent, member).value
        if value in IMPLEMENTED_INTENTS and value not in registered:
            issues.append(
                IntentValidationIssue(
                    "phase56",
                    f"Phase 56 intent {member} ({value!r}) has no registered Action",
                )
            )

    return issues


def validate_phase57_runtime_wiring(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    """Verify Phase 57 realtime voice intents are implemented and registered."""
    from config import IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    for member in PHASE57_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(
                IntentValidationIssue(
                    "phase57",
                    f"Intent enum missing Phase 57 member {member}",
                )
            )
            continue
        value = getattr(Intent, member).value
        if value not in IMPLEMENTED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "phase57",
                    f"Phase 57 intent {member} ({value!r}) missing from IMPLEMENTED_INTENTS",
                )
            )

    if not check_registry:
        return issues

    try:
        from actions.registry import ActionRegistry

        registry = ActionRegistry()
        registered = set(registry._actions.keys())
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase57",
                f"Phase 57 registry load failed: {type(exc).__name__}: {exc}",
            )
        )
        return issues

    try:
        import actions.phase57_actions  # noqa: F401
        import voice.realtime_tts  # noqa: F401
    except Exception as exc:
        issues.append(
            IntentValidationIssue(
                "phase57",
                f"Phase 57 module import failed: {type(exc).__name__}: {exc}",
            )
        )

    for member in PHASE57_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            continue
        value = getattr(Intent, member).value
        if value in IMPLEMENTED_INTENTS and value not in registered:
            issues.append(
                IntentValidationIssue(
                    "phase57",
                    f"Phase 57 intent {member} ({value!r}) has no registered Action",
                )
            )

    return issues


PHASE58_INTENT_MEMBERS: tuple[str, ...] = (
    "SHOW_REALTIME_LATENCY_BREAKDOWN",
    "TEST_WEBSOCKET_REALTIME_VOICE",
    "BENCHMARK_REALTIME_STREAMING",
    "SHOW_RUNTIME_CONFIG_SOURCES",
    "SHOW_RUNTIME_CONFIG_MISMATCHES",
)

PHASE58_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in PHASE58_INTENT_MEMBERS if hasattr(Intent, member)
)


def validate_phase58_runtime_wiring(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    from config import IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    for member in PHASE58_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(IntentValidationIssue("phase58", f"Intent enum missing Phase 58 member {member}"))
            continue
        value = getattr(Intent, member).value
        if value not in IMPLEMENTED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "phase58",
                    f"Phase 58 intent {member} ({value!r}) missing from IMPLEMENTED_INTENTS",
                )
            )
    if not check_registry:
        return issues
    try:
        from actions.registry import ActionRegistry

        registry = ActionRegistry()
        registered = set(registry._actions.keys())
    except Exception as exc:
        issues.append(IntentValidationIssue("phase58", f"Phase 58 registry load failed: {exc}"))
        return issues
    try:
        import actions.phase58_actions  # noqa: F401
        import voice.providers.elevenlabs_websocket  # noqa: F401
        import voice.preemptive_tts  # noqa: F401
    except Exception as exc:
        issues.append(IntentValidationIssue("phase58", f"Phase 58 module import failed: {exc}"))
    for member in PHASE58_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            continue
        value = getattr(Intent, member).value
        if value in IMPLEMENTED_INTENTS and value not in registered:
            issues.append(
                IntentValidationIssue(
                    "phase58",
                    f"Phase 58 intent {member} ({value!r}) has no registered Action",
                )
            )
    return issues


PHASE59_INTENT_MEMBERS: tuple[str, ...] = (
    "SHOW_CONVERSATION_RUNTIME",
    "SHOW_INTERRUPTION_METRICS",
    "SHOW_CONVERSATIONAL_MEMORY",
    "BENCHMARK_FULL_DUPLEX_CONVERSATION",
    "PHASE59_STATUS",
)

PHASE59_INTENT_VALUES: frozenset[str] = frozenset(
    getattr(Intent, member).value for member in PHASE59_INTENT_MEMBERS if hasattr(Intent, member)
)


def validate_phase59_runtime_wiring(*, check_registry: bool = True) -> list[IntentValidationIssue]:
    from config import IMPLEMENTED_INTENTS

    issues: list[IntentValidationIssue] = []
    for member in PHASE59_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            issues.append(IntentValidationIssue("phase59", f"Intent enum missing Phase 59 member {member}"))
            continue
        value = getattr(Intent, member).value
        if value not in IMPLEMENTED_INTENTS:
            issues.append(
                IntentValidationIssue(
                    "phase59",
                    f"Phase 59 intent {member} ({value!r}) missing from IMPLEMENTED_INTENTS",
                )
            )
    if not check_registry:
        return issues
    try:
        from actions.registry import ActionRegistry

        registry = ActionRegistry()
        registered = set(registry._actions.keys())
    except Exception as exc:
        issues.append(IntentValidationIssue("phase59", f"Phase 59 registry load failed: {exc}"))
        return issues
    try:
        import actions.phase59_actions  # noqa: F401
        import conversation.human_runtime  # noqa: F401
        import conversation.llm_streaming  # noqa: F401
        import voice.continuous_mic  # noqa: F401
    except Exception as exc:
        issues.append(IntentValidationIssue("phase59", f"Phase 59 module import failed: {exc}"))
    for member in PHASE59_INTENT_MEMBERS:
        if not hasattr(Intent, member):
            continue
        value = getattr(Intent, member).value
        if value in IMPLEMENTED_INTENTS and value not in registered:
            issues.append(
                IntentValidationIssue(
                    "phase59",
                    f"Phase 59 intent {member} ({value!r}) has no registered Action",
                )
            )
    return issues


def format_validation_report(issues: list[IntentValidationIssue]) -> str:
    if not issues:
        return "Intent registry consistency: OK"
    lines = ["Intent registry consistency: FAIL", f"Issues ({len(issues)}):"]
    lines.extend(f"  - {issue.format()}" for issue in issues)
    return "\n".join(lines)


def run_startup_intent_validation(*, strict: bool = True) -> list[IntentValidationIssue]:
    """
    Run full consistency validation during startup.
    When strict=True, raises StartupError with readable output if issues exist.
    """
    from core.startup import StartupError

    enum_issues = validate_required_intent_enums()
    if enum_issues:
        report = format_validation_report(enum_issues)
        if strict:
            raise StartupError(report)
        return enum_issues

    # Import phrase/classifier modules (safe once enum members exist).
    import brain.english_voice_phrases  # noqa: F401
    import brain.intent_classifier  # noqa: F401

    issues = validate_intent_registry_consistency()
    issues.extend(validate_phase55_runtime_wiring())
    issues.extend(validate_phase56_runtime_wiring())
    issues.extend(validate_phase57_runtime_wiring())
    issues.extend(validate_phase58_runtime_wiring())
    issues.extend(validate_phase59_runtime_wiring())
    issues.extend(validate_patch_workflow_phrase_collisions())
    from brain.operational_command_phrases import validate_operational_phrase_collisions

    for message in validate_operational_phrase_collisions():
        issues.append(IntentValidationIssue("operational_phrases", message))
    if issues and strict:
        raise StartupError(format_validation_report(issues))
    return issues
