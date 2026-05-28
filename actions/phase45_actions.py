"""Phase 45 read-only project/trading investigation actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_confirmation_required, result_success
from core.types import CommandRequest, CommandResult, Intent
from phase45_investigation import (
    build_investigation_graph,
    compare_live_vs_backtest,
    diff_live_and_backtest_logic,
    explain_latest_error,
    find_failing_tests,
    find_recent_code_changes,
    generate_findings_report,
    hunt_algorithm_bugs,
    inspect_latest_backtest_report,
    inspect_latest_live_report,
    inspect_project,
    investigate_trading_mismatch,
    phase45_status,
    phase46_status,
    plan_verification_run,
    propose_algorithm_patch,
    propose_investigation_plan,
    run_safe_diagnostics,
    search_investigation_graph,
    show_investigation_graph,
    summarize_current_project,
    trace_algorithm_behavior,
)
from investigation.replay_report import (
    build_verification_fixture_command,
    export_replay_snapshot_command,
    investigation_confidence_report_command,
    replay_latest_signal_command,
    replay_live_vs_backtest_command,
    replay_symbol_command,
    show_causality_graph_command,
    show_replay_diff_command,
    show_replay_timeline_command,
    trace_execution_lifecycle_command,
    trace_signal_lifecycle_command,
    verify_all_hypotheses_command,
    verify_top_hypothesis_command,
)
from investigation.patch_simulation import (
    approve_patch_apply,
    compare_replay_before_after,
    estimate_patch_impact,
    format_patch_candidates,
    generate_patch_simulation_report,
    reject_patch_apply,
    run_patch_simulation,
    show_patch_simulation,
    upgraded_patch_proposal,
    format_patch_simulation,
)
from investigation.historical_validation import (
    compare_strategy_metrics_before_after,
    estimate_production_risk,
    export_validation_sweep,
    recommend_production_action,
    run_historical_validation_sweep,
    show_investigation_summary,
    show_validation_sweep,
    show_worst_divergence_symbols,
)
from investigation.price_integrity import (
    audit_price_integrity,
    check_adjusted_price_usage,
    check_duplicate_bars,
    check_timestamp_alignment,
    compare_candle_sources,
    find_close_price_mismatches,
    generate_price_integrity_report,
    inspect_data_cache_drift,
    trace_price_source,
)
from investigation.execution_investigation import (
    audit_execution_path,
    compare_signal_count_to_order_attempts,
    explain_zero_execution_attempts,
    generate_execution_investigation_report,
    inspect_execution_adapter,
    rank_execution_block_reasons,
    show_execution_blockers,
    trace_signal_to_order,
)
from investigation.execution_flow import (
    explain_top_execution_blocker,
    generate_execution_flow_report,
    propose_execution_fix,
    rank_dead_signal_causes,
    reconstruct_execution_flow,
    show_signal_lifecycle_timeline,
    simulate_unblock_scenario,
    trace_blocked_signal,
    trace_signal_to_execution,
)
from investigation.execution_cleanup import (
    compare_risk_before_after_cleanup,
    generate_execution_cleanup_report,
    propose_execution_cleanup_patch,
    show_stale_open_positions,
    simulate_execution_cleanup_patch,
)
from investigation.patch_apply import (
    apply_approved_patch,
    compare_pre_post_patch,
    replay_after_patch,
    rollback_last_patch,
    run_patch_workflow,
    show_approved_patch,
    show_patch_history,
    show_patch_workflow_status,
    validate_applied_patch,
    validate_patch_safety,
)


class _ReadOnlyPhase45Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class Phase45StatusAction(_ReadOnlyPhase45Action):
    intent = Intent.PHASE45_STATUS.value
    _fn = staticmethod(phase45_status)


class Phase46StatusAction(_ReadOnlyPhase45Action):
    intent = Intent.PHASE46_STATUS.value
    _fn = staticmethod(phase46_status)


class InspectProjectAction(_ReadOnlyPhase45Action):
    intent = Intent.INSPECT_PROJECT.value
    _fn = staticmethod(inspect_project)


class SummarizeCurrentProjectAction(_ReadOnlyPhase45Action):
    intent = Intent.SUMMARIZE_CURRENT_PROJECT.value
    _fn = staticmethod(summarize_current_project)


class FindFailingTestsPhase45Action(_ReadOnlyPhase45Action):
    intent = Intent.FIND_FAILING_TESTS.value
    _fn = staticmethod(find_failing_tests)


class ExplainLatestErrorAction(_ReadOnlyPhase45Action):
    intent = Intent.EXPLAIN_LATEST_ERROR.value
    _fn = staticmethod(explain_latest_error)


class InvestigateTradingMismatchAction(_ReadOnlyPhase45Action):
    intent = Intent.INVESTIGATE_TRADING_MISMATCH.value
    _fn = staticmethod(investigate_trading_mismatch)


class CompareLiveVsBacktestAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_LIVE_VS_BACKTEST.value
    _fn = staticmethod(compare_live_vs_backtest)


class InspectLatestLiveReportAction(_ReadOnlyPhase45Action):
    intent = Intent.INSPECT_LATEST_LIVE_REPORT.value
    _fn = staticmethod(inspect_latest_live_report)


class InspectLatestBacktestReportAction(_ReadOnlyPhase45Action):
    intent = Intent.INSPECT_LATEST_BACKTEST_REPORT.value
    _fn = staticmethod(inspect_latest_backtest_report)


class FindRecentCodeChangesAction(_ReadOnlyPhase45Action):
    intent = Intent.FIND_RECENT_CODE_CHANGES.value
    _fn = staticmethod(find_recent_code_changes)


class ProposeInvestigationPlanAction(_ReadOnlyPhase45Action):
    intent = Intent.PROPOSE_INVESTIGATION_PLAN.value
    _fn = staticmethod(propose_investigation_plan)


class RunSafeDiagnosticsAction(_ReadOnlyPhase45Action):
    intent = Intent.RUN_SAFE_DIAGNOSTICS.value
    _fn = staticmethod(run_safe_diagnostics)


class GenerateFindingsReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_FINDINGS_REPORT.value
    _fn = staticmethod(generate_findings_report)


class BuildInvestigationGraphAction(_ReadOnlyPhase45Action):
    intent = Intent.BUILD_INVESTIGATION_GRAPH.value
    _fn = staticmethod(build_investigation_graph)


class ShowInvestigationGraphAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_INVESTIGATION_GRAPH.value
    _fn = staticmethod(show_investigation_graph)


class SearchInvestigationGraphAction(BaseAction):
    intent = Intent.SEARCH_INVESTIGATION_GRAPH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = str(request.params.get("query") or request.raw_text or "")
        for prefix in ("search investigation graph", "search graph"):
            if query.lower().startswith(prefix):
                query = query[len(prefix) :].strip()
        body = search_investigation_graph(query)
        return result_success(Intent.SEARCH_INVESTIGATION_GRAPH, body, data={"read_only": True, "query": query})


class TraceAlgorithmBehaviorAction(_ReadOnlyPhase45Action):
    intent = Intent.TRACE_ALGORITHM_BEHAVIOR.value
    _fn = staticmethod(trace_algorithm_behavior)


class DiffLiveBacktestLogicAction(_ReadOnlyPhase45Action):
    intent = Intent.DIFF_LIVE_BACKTEST_LOGIC.value
    _fn = staticmethod(diff_live_and_backtest_logic)


class HuntAlgorithmBugsAction(_ReadOnlyPhase45Action):
    intent = Intent.HUNT_ALGORITHM_BUGS.value
    _fn = staticmethod(hunt_algorithm_bugs)


class ProposeAlgorithmPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.PROPOSE_ALGORITHM_PATCH.value
    _fn = staticmethod(upgraded_patch_proposal)


class PlanVerificationRunAction(_ReadOnlyPhase45Action):
    intent = Intent.PLAN_VERIFICATION_RUN.value
    _fn = staticmethod(plan_verification_run)


def _symbol_from_request(request: CommandRequest, *, default: str = "AAPL") -> str:
    symbol = str(request.params.get("symbol") or "").strip()
    if symbol:
        return symbol.upper()
    raw = (request.raw_text or "").strip()
    for prefix in (
        "replay live vs backtest",
        "replay symbol",
        "show replay diff",
        "trace signal lifecycle",
        "trace execution lifecycle",
        "show causality graph",
        "build verification fixture",
        "export replay snapshot",
    ):
        if raw.lower().startswith(prefix):
            tail = raw[len(prefix) :].strip()
            if tail:
                return tail.split()[0].upper()
    return default


class ReplaySymbolAction(BaseAction):
    intent = Intent.REPLAY_SYMBOL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.REPLAY_SYMBOL, replay_symbol_command(symbol), data={"read_only": True, "symbol": symbol})


class ReplayLatestSignalAction(_ReadOnlyPhase45Action):
    intent = Intent.REPLAY_LATEST_SIGNAL.value
    _fn = staticmethod(replay_latest_signal_command)


class ReplayLiveVsBacktestAction(BaseAction):
    intent = Intent.REPLAY_LIVE_VS_BACKTEST.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.REPLAY_LIVE_VS_BACKTEST, replay_live_vs_backtest_command(symbol), data={"read_only": True, "symbol": symbol})


class VerifyTopHypothesisAction(_ReadOnlyPhase45Action):
    intent = Intent.VERIFY_TOP_HYPOTHESIS.value
    _fn = staticmethod(verify_top_hypothesis_command)


class VerifyAllHypothesesAction(_ReadOnlyPhase45Action):
    intent = Intent.VERIFY_ALL_HYPOTHESES.value
    _fn = staticmethod(verify_all_hypotheses_command)


class ShowReplayTimelineAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_REPLAY_TIMELINE.value
    _fn = staticmethod(show_replay_timeline_command)


class ShowReplayDiffAction(BaseAction):
    intent = Intent.SHOW_REPLAY_DIFF.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.SHOW_REPLAY_DIFF, show_replay_diff_command(symbol), data={"read_only": True, "symbol": symbol})


class BuildVerificationFixtureAction(BaseAction):
    intent = Intent.BUILD_VERIFICATION_FIXTURE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.BUILD_VERIFICATION_FIXTURE, build_verification_fixture_command(symbol), data={"read_only": True, "symbol": symbol})


class ExportReplaySnapshotAction(BaseAction):
    intent = Intent.EXPORT_REPLAY_SNAPSHOT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.EXPORT_REPLAY_SNAPSHOT, export_replay_snapshot_command(symbol), data={"read_only": True, "symbol": symbol})


class TraceSignalLifecycleAction(BaseAction):
    intent = Intent.TRACE_SIGNAL_LIFECYCLE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.TRACE_SIGNAL_LIFECYCLE, trace_signal_lifecycle_command(symbol), data={"read_only": True, "symbol": symbol})


class TraceExecutionLifecycleAction(BaseAction):
    intent = Intent.TRACE_EXECUTION_LIFECYCLE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.TRACE_EXECUTION_LIFECYCLE, trace_execution_lifecycle_command(symbol), data={"read_only": True, "symbol": symbol})


class ShowCausalityGraphAction(BaseAction):
    intent = Intent.SHOW_CAUSALITY_GRAPH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        symbol = _symbol_from_request(request)
        return result_success(Intent.SHOW_CAUSALITY_GRAPH, show_causality_graph_command(symbol), data={"read_only": True, "symbol": symbol})


class InvestigationConfidenceReportAction(_ReadOnlyPhase45Action):
    intent = Intent.INVESTIGATION_CONFIDENCE_REPORT.value
    _fn = staticmethod(investigation_confidence_report_command)


class SimulatePatchTopHypothesisAction(_ReadOnlyPhase45Action):
    intent = Intent.SIMULATE_PATCH_TOP_HYPOTHESIS.value
    _fn = staticmethod(format_patch_candidates)


class RunPatchSimulationAction(_ReadOnlyPhase45Action):
    intent = Intent.RUN_PATCH_SIMULATION.value

    @staticmethod
    def _fn() -> str:
        return format_patch_simulation(run_patch_simulation())


class CompareReplayBeforeAfterAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_REPLAY_BEFORE_AFTER.value
    _fn = staticmethod(compare_replay_before_after)


class EstimatePatchImpactAction(_ReadOnlyPhase45Action):
    intent = Intent.ESTIMATE_PATCH_IMPACT.value
    _fn = staticmethod(estimate_patch_impact)


class GeneratePatchSimulationReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_PATCH_SIMULATION_REPORT.value
    _fn = staticmethod(generate_patch_simulation_report)


class ShowPatchSimulationAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_PATCH_SIMULATION.value
    _fn = staticmethod(show_patch_simulation)


class ApprovePatchApplyAction(_ReadOnlyPhase45Action):
    intent = Intent.APPROVE_PATCH_APPLY.value
    _fn = staticmethod(approve_patch_apply)


class RejectPatchApplyAction(_ReadOnlyPhase45Action):
    intent = Intent.REJECT_PATCH_APPLY.value
    _fn = staticmethod(reject_patch_apply)


class RunHistoricalValidationSweepAction(_ReadOnlyPhase45Action):
    intent = Intent.RUN_HISTORICAL_VALIDATION_SWEEP.value

    @staticmethod
    def _fn() -> str:
        run_historical_validation_sweep()
        return show_validation_sweep()


class ShowValidationSweepAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_VALIDATION_SWEEP.value
    _fn = staticmethod(show_validation_sweep)


class ExportValidationSweepAction(_ReadOnlyPhase45Action):
    intent = Intent.EXPORT_VALIDATION_SWEEP.value
    _fn = staticmethod(export_validation_sweep)


class CompareStrategyMetricsBeforeAfterAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_STRATEGY_METRICS_BEFORE_AFTER.value
    _fn = staticmethod(compare_strategy_metrics_before_after)


class ShowWorstDivergenceSymbolsAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_WORST_DIVERGENCE_SYMBOLS.value
    _fn = staticmethod(show_worst_divergence_symbols)


class EstimateProductionRiskAction(_ReadOnlyPhase45Action):
    intent = Intent.ESTIMATE_PRODUCTION_RISK.value
    _fn = staticmethod(estimate_production_risk)


class RecommendProductionActionAction(_ReadOnlyPhase45Action):
    intent = Intent.RECOMMEND_PRODUCTION_ACTION.value
    _fn = staticmethod(recommend_production_action)


class ShowInvestigationSummaryAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_INVESTIGATION_SUMMARY.value
    _fn = staticmethod(show_investigation_summary)


class AuditPriceIntegrityAction(_ReadOnlyPhase45Action):
    intent = Intent.AUDIT_PRICE_INTEGRITY.value
    _fn = staticmethod(audit_price_integrity)


class CompareCandleSourcesAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_CANDLE_SOURCES.value
    _fn = staticmethod(compare_candle_sources)


class TracePriceSourceAction(BaseAction):
    intent = Intent.TRACE_PRICE_SOURCE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip()
        symbol = str(request.params.get("symbol") or "").strip().upper()
        if not symbol and raw.lower().startswith("trace price source"):
            tail = raw[len("trace price source") :].strip()
            symbol = tail.split()[0].upper() if tail else "AAPL"
        symbol = symbol or "AAPL"
        return result_success(Intent.TRACE_PRICE_SOURCE, trace_price_source(symbol), data={"read_only": True, "symbol": symbol})


class FindClosePriceMismatchesAction(_ReadOnlyPhase45Action):
    intent = Intent.FIND_CLOSE_PRICE_MISMATCHES.value
    _fn = staticmethod(find_close_price_mismatches)


class InspectDataCacheDriftAction(_ReadOnlyPhase45Action):
    intent = Intent.INSPECT_DATA_CACHE_DRIFT.value
    _fn = staticmethod(inspect_data_cache_drift)


class CheckTimestampAlignmentAction(_ReadOnlyPhase45Action):
    intent = Intent.CHECK_TIMESTAMP_ALIGNMENT.value
    _fn = staticmethod(check_timestamp_alignment)


class CheckAdjustedPriceUsageAction(_ReadOnlyPhase45Action):
    intent = Intent.CHECK_ADJUSTED_PRICE_USAGE.value
    _fn = staticmethod(check_adjusted_price_usage)


class CheckDuplicateBarsAction(_ReadOnlyPhase45Action):
    intent = Intent.CHECK_DUPLICATE_BARS.value
    _fn = staticmethod(check_duplicate_bars)


class GeneratePriceIntegrityReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_PRICE_INTEGRITY_REPORT.value
    _fn = staticmethod(generate_price_integrity_report)


class AuditExecutionPathAction(_ReadOnlyPhase45Action):
    intent = Intent.AUDIT_EXECUTION_PATH.value
    _fn = staticmethod(audit_execution_path)


class ExplainZeroExecutionAttemptsAction(_ReadOnlyPhase45Action):
    intent = Intent.EXPLAIN_ZERO_EXECUTION_ATTEMPTS.value
    _fn = staticmethod(explain_zero_execution_attempts)


class TraceSignalToOrderAction(BaseAction):
    intent = Intent.TRACE_SIGNAL_TO_ORDER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip()
        symbol = str(request.params.get("symbol") or "").strip().upper()
        if not symbol and raw.lower().startswith("trace signal to order"):
            tail = raw[len("trace signal to order") :].strip()
            symbol = tail.split()[0].upper() if tail else "AAPL"
        symbol = symbol or "AAPL"
        return result_success(
            Intent.TRACE_SIGNAL_TO_ORDER,
            trace_signal_to_order(symbol),
            data={"read_only": True, "symbol": symbol},
        )


class ShowExecutionBlockersAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_EXECUTION_BLOCKERS.value
    _fn = staticmethod(show_execution_blockers)


class RankExecutionBlockReasonsAction(_ReadOnlyPhase45Action):
    intent = Intent.RANK_EXECUTION_BLOCK_REASONS.value
    _fn = staticmethod(rank_execution_block_reasons)


class InspectExecutionAdapterAction(_ReadOnlyPhase45Action):
    intent = Intent.INSPECT_EXECUTION_ADAPTER.value
    _fn = staticmethod(inspect_execution_adapter)


class CompareSignalCountToOrderAttemptsAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_SIGNAL_COUNT_TO_ORDER_ATTEMPTS.value
    _fn = staticmethod(compare_signal_count_to_order_attempts)


class GenerateExecutionInvestigationReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_EXECUTION_INVESTIGATION_REPORT.value
    _fn = staticmethod(generate_execution_investigation_report)


class TraceSignalToExecutionAction(BaseAction):
    intent = Intent.TRACE_SIGNAL_TO_EXECUTION.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip()
        symbol = str(request.params.get("symbol") or "").strip().upper()
        if not symbol and raw.lower().startswith("trace signal to execution"):
            tail = raw[len("trace signal to execution") :].strip()
            symbol = tail.split()[0].upper() if tail else "AAPL"
        symbol = symbol or "AAPL"
        return result_success(
            Intent.TRACE_SIGNAL_TO_EXECUTION,
            trace_signal_to_execution(symbol),
            data={"read_only": True, "symbol": symbol},
        )


class TraceBlockedSignalAction(BaseAction):
    intent = Intent.TRACE_BLOCKED_SIGNAL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip()
        symbol = str(request.params.get("symbol") or "").strip().upper()
        if not symbol and raw.lower().startswith("trace blocked signal"):
            tail = raw[len("trace blocked signal") :].strip()
            symbol = tail.split()[0].upper() if tail else "AAPL"
        symbol = symbol or "AAPL"
        return result_success(
            Intent.TRACE_BLOCKED_SIGNAL,
            trace_blocked_signal(symbol),
            data={"read_only": True, "symbol": symbol},
        )


class ExplainTopExecutionBlockerAction(_ReadOnlyPhase45Action):
    intent = Intent.EXPLAIN_TOP_EXECUTION_BLOCKER.value
    _fn = staticmethod(explain_top_execution_blocker)


class ReconstructExecutionFlowAction(_ReadOnlyPhase45Action):
    intent = Intent.RECONSTRUCT_EXECUTION_FLOW.value
    _fn = staticmethod(reconstruct_execution_flow)


class ShowSignalLifecycleTimelineAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_SIGNAL_LIFECYCLE_TIMELINE.value
    _fn = staticmethod(show_signal_lifecycle_timeline)


class RankDeadSignalCausesAction(_ReadOnlyPhase45Action):
    intent = Intent.RANK_DEAD_SIGNAL_CAUSES.value
    _fn = staticmethod(rank_dead_signal_causes)


class SimulateUnblockScenarioAction(BaseAction):
    intent = Intent.SIMULATE_UNBLOCK_SCENARIO.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").strip().lower()
        scenario = str(request.params.get("scenario") or "top").strip()
        if raw.startswith("simulate unblock scenario"):
            tail = raw[len("simulate unblock scenario") :].strip()
            if tail:
                scenario = tail
        return result_success(
            Intent.SIMULATE_UNBLOCK_SCENARIO,
            simulate_unblock_scenario(scenario),
            data={"read_only": True, "scenario": scenario},
        )


class ProposeExecutionFixAction(_ReadOnlyPhase45Action):
    intent = Intent.PROPOSE_EXECUTION_FIX.value
    _fn = staticmethod(propose_execution_fix)


class GenerateExecutionFlowReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_EXECUTION_FLOW_REPORT.value
    _fn = staticmethod(generate_execution_flow_report)


class SimulateExecutionCleanupPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.SIMULATE_EXECUTION_CLEANUP_PATCH.value
    _fn = staticmethod(simulate_execution_cleanup_patch)


class CompareRiskBeforeAfterCleanupAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_RISK_BEFORE_AFTER_CLEANUP.value
    _fn = staticmethod(compare_risk_before_after_cleanup)


class ShowStaleOpenPositionsAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_STALE_OPEN_POSITIONS.value
    _fn = staticmethod(show_stale_open_positions)


class ProposeExecutionCleanupPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.PROPOSE_EXECUTION_CLEANUP_PATCH.value
    _fn = staticmethod(propose_execution_cleanup_patch)


class GenerateExecutionCleanupReportAction(_ReadOnlyPhase45Action):
    intent = Intent.GENERATE_EXECUTION_CLEANUP_REPORT.value
    _fn = staticmethod(generate_execution_cleanup_report)


class ShowApprovedPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_APPROVED_PATCH.value
    _fn = staticmethod(show_approved_patch)


class ValidatePatchSafetyAction(_ReadOnlyPhase45Action):
    intent = Intent.VALIDATE_PATCH_SAFETY.value
    _fn = staticmethod(validate_patch_safety)


class ApplyApprovedPatchAction(BaseAction):
    intent = Intent.APPLY_APPROVED_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        import config

        if not getattr(config, "PATCH_APPLY_ENABLED", True):
            return result_success(
                Intent.APPLY_APPROVED_PATCH,
                "Patch apply is disabled (PATCH_APPLY_ENABLED=false).",
                data={"blocked": True},
            )
        raw = (request.raw_text or "").lower()
        confirmed = bool(request.confirmed or "confirm" in raw or raw.strip().endswith(" yes"))
        if not confirmed:
            return result_confirmation_required(
                Intent.APPLY_APPROVED_PATCH,
                "Apply approved patch requires explicit confirmation (paper-only operational fix).",
                confirmation_id="apply_approved_patch",
            )
        body = apply_approved_patch(confirmed=True, approver="operator")
        return result_success(Intent.APPLY_APPROVED_PATCH, body, data={"confirmed": True, "paper_only": True})


class RollbackLastPatchAction(BaseAction):
    intent = Intent.ROLLBACK_LAST_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        raw = (request.raw_text or "").lower()
        confirmed = bool(request.confirmed or "confirm" in raw or raw.strip().endswith(" yes"))
        if not confirmed:
            return result_confirmation_required(
                Intent.ROLLBACK_LAST_PATCH,
                "Rollback last patch requires explicit confirmation.",
                confirmation_id="rollback_last_patch",
            )
        body = rollback_last_patch(confirmed=True)
        return result_success(Intent.ROLLBACK_LAST_PATCH, body, data={"confirmed": True})


class ShowPatchHistoryAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_PATCH_HISTORY.value
    _fn = staticmethod(show_patch_history)


class ValidateAppliedPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.VALIDATE_APPLIED_PATCH.value
    _fn = staticmethod(validate_applied_patch)


class ReplayAfterPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.REPLAY_AFTER_PATCH.value
    _fn = staticmethod(replay_after_patch)


class ComparePrePostPatchAction(_ReadOnlyPhase45Action):
    intent = Intent.COMPARE_PRE_POST_PATCH.value
    _fn = staticmethod(compare_pre_post_patch)


class ShowPatchWorkflowStatusAction(_ReadOnlyPhase45Action):
    intent = Intent.SHOW_PATCH_WORKFLOW_STATUS.value
    _fn = staticmethod(show_patch_workflow_status)


class RunPatchWorkflowAction(BaseAction):
    intent = Intent.RUN_PATCH_WORKFLOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        import config

        if not getattr(config, "PATCH_APPLY_ENABLED", True):
            return result_success(
                Intent.RUN_PATCH_WORKFLOW,
                "Patch workflow is disabled (PATCH_APPLY_ENABLED=false).",
                data={"blocked": True},
            )
        raw = (request.raw_text or "").lower()
        confirmed = bool(request.confirmed or "confirm" in raw or raw.strip().endswith(" yes"))
        if not confirmed:
            body = run_patch_workflow(confirmed=False)
            return result_confirmation_required(
                Intent.RUN_PATCH_WORKFLOW,
                body,
                confirmation_id="run_patch_workflow",
            )
        body = run_patch_workflow(confirmed=True)
        return result_success(Intent.RUN_PATCH_WORKFLOW, body, data={"confirmed": True, "paper_only": True})
