"""Phase 55 autonomous root cause verification actions."""

from __future__ import annotations

from actions.base import BaseAction
from assistant.confidence_tracking import (
    compare_root_cause_confidence,
    explain_confidence_changes,
    show_confidence_evolution,
)
from assistant.contradiction_engine import (
    explain_contradiction,
    resolve_contradiction,
    show_contradictory_evidence,
)
from assistant.experiment_engine import (
    explain_experiment_impact,
    run_safe_experiment_simulation,
    suggest_experiments,
)
from assistant.investigation_graph import (
    explain_investigation_graph,
    show_investigation_graph,
    trace_causal_chain,
)
from assistant.operational_comparison import (
    compare_before_after_cleanup,
    compare_investigation_periods,
    compare_operational_periods,
)
from assistant.root_cause_engine import verify_root_causes_now
from assistant.root_cause_summary import (
    explain_dominant_root_cause,
    explain_operational_failures,
    explain_why_trades_are_blocked,
    summarize_root_causes,
    summarize_verified_findings,
)
from assistant.verification_plans import (
    explain_verification_plan,
    run_verification_plan_now,
    show_verification_plans,
)
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent


class _ReadOnlyPhase55Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowVerificationPlansAction(_ReadOnlyPhase55Action):
    intent = Intent.SHOW_VERIFICATION_PLANS.value
    _fn = staticmethod(show_verification_plans)


class ExplainVerificationPlanAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_VERIFICATION_PLAN.value
    _fn = staticmethod(explain_verification_plan)


class RunVerificationPlanAction(_ReadOnlyPhase55Action):
    intent = Intent.RUN_VERIFICATION_PLAN.value
    _fn = staticmethod(run_verification_plan_now)


class VerifyRootCausesAction(_ReadOnlyPhase55Action):
    intent = Intent.VERIFY_ROOT_CAUSES.value
    _fn = staticmethod(verify_root_causes_now)


class ShowConfidenceEvolutionAction(_ReadOnlyPhase55Action):
    intent = Intent.SHOW_CONFIDENCE_EVOLUTION.value
    _fn = staticmethod(show_confidence_evolution)


class ExplainConfidenceChangesAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_CONFIDENCE_CHANGES.value
    _fn = staticmethod(explain_confidence_changes)


class CompareRootCauseConfidenceAction(_ReadOnlyPhase55Action):
    intent = Intent.COMPARE_ROOT_CAUSE_CONFIDENCE.value
    _fn = staticmethod(compare_root_cause_confidence)


class ShowContradictoryEvidenceAction(_ReadOnlyPhase55Action):
    intent = Intent.SHOW_CONTRADICTORY_EVIDENCE.value
    _fn = staticmethod(show_contradictory_evidence)


class ExplainContradictionAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_CONTRADICTION.value
    _fn = staticmethod(explain_contradiction)


class ResolveContradictionAction(_ReadOnlyPhase55Action):
    intent = Intent.RESOLVE_CONTRADICTION.value
    _fn = staticmethod(resolve_contradiction)


class SuggestExperimentsAction(_ReadOnlyPhase55Action):
    intent = Intent.SUGGEST_EXPERIMENTS.value
    _fn = staticmethod(suggest_experiments)


class ExplainExperimentImpactAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_EXPERIMENT_IMPACT.value
    _fn = staticmethod(explain_experiment_impact)


class RunSafeExperimentSimulationAction(_ReadOnlyPhase55Action):
    intent = Intent.RUN_SAFE_EXPERIMENT_SIMULATION.value
    _fn = staticmethod(run_safe_experiment_simulation)


class ShowRootCauseGraphAction(_ReadOnlyPhase55Action):
    intent = Intent.SHOW_ROOT_CAUSE_GRAPH.value
    _fn = staticmethod(show_investigation_graph)


class ExplainRootCauseGraphAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_ROOT_CAUSE_GRAPH.value
    _fn = staticmethod(explain_investigation_graph)


class TraceCausalChainAction(_ReadOnlyPhase55Action):
    intent = Intent.TRACE_CAUSAL_CHAIN.value
    _fn = staticmethod(trace_causal_chain)


class SummarizeRootCausesAction(_ReadOnlyPhase55Action):
    intent = Intent.SUMMARIZE_ROOT_CAUSES.value
    _fn = staticmethod(summarize_root_causes)


class ExplainDominantRootCauseAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_DOMINANT_ROOT_CAUSE.value
    _fn = staticmethod(explain_dominant_root_cause)


class ExplainOperationalFailuresAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_OPERATIONAL_FAILURES.value
    _fn = staticmethod(explain_operational_failures)


class SummarizeVerifiedFindingsAction(_ReadOnlyPhase55Action):
    intent = Intent.SUMMARIZE_VERIFIED_FINDINGS.value
    _fn = staticmethod(summarize_verified_findings)


class ExplainWhyTradesAreBlockedAction(_ReadOnlyPhase55Action):
    intent = Intent.EXPLAIN_WHY_TRADES_ARE_BLOCKED.value
    _fn = staticmethod(explain_why_trades_are_blocked)


class CompareOperationalPeriodsAction(_ReadOnlyPhase55Action):
    intent = Intent.COMPARE_OPERATIONAL_PERIODS.value
    _fn = staticmethod(compare_operational_periods)


class CompareBeforeAfterCleanupAction(_ReadOnlyPhase55Action):
    intent = Intent.COMPARE_BEFORE_AFTER_CLEANUP.value
    _fn = staticmethod(compare_before_after_cleanup)


class CompareInvestigationPeriodsAction(_ReadOnlyPhase55Action):
    intent = Intent.COMPARE_INVESTIGATION_PERIODS.value
    _fn = staticmethod(compare_investigation_periods)
