"""Phase 54 autonomous investigation actions."""

from __future__ import annotations

from actions.base import BaseAction
from assistant.hypothesis_engine import (
    compare_hypothesis_history,
    explain_top_hypothesis,
    show_active_hypotheses,
    verify_active_hypotheses,
)
from assistant.intelligence_timeline import (
    compare_today_vs_yesterday_intelligence,
    explain_recent_anomalies,
    show_intelligence_timeline,
)
from assistant.investigation_cycles import (
    summarize_autonomous_findings,
    summarize_operational_anomalies,
)
from assistant.investigation_scheduler import (
    pause_investigation_loop,
    resume_investigation_loop,
    run_investigation_cycle_now,
    run_nightly_investigation_now,
    show_investigation_schedule,
)
from core.results import result_success
from core.types import CommandRequest, CommandResult, Intent
from investigation.blocker_trends import (
    compare_blocker_trends,
    explain_dominant_blocker,
    show_blocker_history,
    show_blocker_trends,
)
from investigation.divergence_clustering import (
    cluster_replay_divergences,
    explain_largest_divergence_cluster,
    show_divergence_clusters,
)


class _ReadOnlyPhase54Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowInvestigationScheduleAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_INVESTIGATION_SCHEDULE.value
    _fn = staticmethod(show_investigation_schedule)


class RunInvestigationCycleAction(_ReadOnlyPhase54Action):
    intent = Intent.RUN_INVESTIGATION_CYCLE.value
    _fn = staticmethod(run_investigation_cycle_now)


class PauseInvestigationLoopAction(_ReadOnlyPhase54Action):
    intent = Intent.PAUSE_INVESTIGATION_LOOP.value
    _fn = staticmethod(pause_investigation_loop)


class ResumeInvestigationLoopAction(_ReadOnlyPhase54Action):
    intent = Intent.RESUME_INVESTIGATION_LOOP.value
    _fn = staticmethod(resume_investigation_loop)


class RunNightlyInvestigationNowAction(_ReadOnlyPhase54Action):
    intent = Intent.RUN_NIGHTLY_INVESTIGATION_NOW.value
    _fn = staticmethod(run_nightly_investigation_now)


class ShowBlockerTrendsAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_BLOCKER_TRENDS.value
    _fn = staticmethod(show_blocker_trends)


class CompareBlockerTrendsAction(_ReadOnlyPhase54Action):
    intent = Intent.COMPARE_BLOCKER_TRENDS.value
    _fn = staticmethod(compare_blocker_trends)


class ExplainDominantBlockerAction(_ReadOnlyPhase54Action):
    intent = Intent.EXPLAIN_DOMINANT_BLOCKER.value
    _fn = staticmethod(explain_dominant_blocker)


class ShowBlockerHistoryAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_BLOCKER_HISTORY.value
    _fn = staticmethod(show_blocker_history)


class ClusterReplayDivergencesAction(_ReadOnlyPhase54Action):
    intent = Intent.CLUSTER_REPLAY_DIVERGENCES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        payload = cluster_replay_divergences()
        body = show_divergence_clusters() if payload.get("clusters") else "No replay divergences clustered."
        return result_success(Intent.CLUSTER_REPLAY_DIVERGENCES, body, data={"read_only": True})


class ShowDivergenceClustersAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_DIVERGENCE_CLUSTERS.value
    _fn = staticmethod(show_divergence_clusters)


class ExplainLargestDivergenceClusterAction(_ReadOnlyPhase54Action):
    intent = Intent.EXPLAIN_LARGEST_DIVERGENCE_CLUSTER.value
    _fn = staticmethod(explain_largest_divergence_cluster)


class ShowActiveHypothesesAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_ACTIVE_HYPOTHESES.value
    _fn = staticmethod(show_active_hypotheses)


class VerifyActiveHypothesesAction(_ReadOnlyPhase54Action):
    intent = Intent.VERIFY_ACTIVE_HYPOTHESES.value
    _fn = staticmethod(verify_active_hypotheses)


class ExplainAutonomousTopHypothesisAction(_ReadOnlyPhase54Action):
    intent = Intent.EXPLAIN_AUTONOMOUS_TOP_HYPOTHESIS.value
    _fn = staticmethod(explain_top_hypothesis)


class CompareHypothesisHistoryAction(_ReadOnlyPhase54Action):
    intent = Intent.COMPARE_HYPOTHESIS_HISTORY.value
    _fn = staticmethod(compare_hypothesis_history)


class ShowIntelligenceTimelineAction(_ReadOnlyPhase54Action):
    intent = Intent.SHOW_INTELLIGENCE_TIMELINE.value
    _fn = staticmethod(show_intelligence_timeline)


class ExplainRecentAnomaliesAction(_ReadOnlyPhase54Action):
    intent = Intent.EXPLAIN_RECENT_ANOMALIES.value
    _fn = staticmethod(explain_recent_anomalies)


class CompareTodayVsYesterdayIntelligenceAction(_ReadOnlyPhase54Action):
    intent = Intent.COMPARE_TODAY_VS_YESTERDAY_INTELLIGENCE.value
    _fn = staticmethod(compare_today_vs_yesterday_intelligence)


class SummarizeAutonomousFindingsAction(_ReadOnlyPhase54Action):
    intent = Intent.SUMMARIZE_AUTONOMOUS_FINDINGS.value
    _fn = staticmethod(summarize_autonomous_findings)


class SummarizeOperationalAnomaliesAction(_ReadOnlyPhase54Action):
    intent = Intent.SUMMARIZE_OPERATIONAL_ANOMALIES.value
    _fn = staticmethod(summarize_operational_anomalies)


class ExplainCurrentTradingRiskAction(_ReadOnlyPhase54Action):
    intent = Intent.EXPLAIN_CURRENT_TRADING_RISK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        try:
            from operational.trading_operations import show_current_execution_risk

            body = show_current_execution_risk()
        except Exception as exc:
            body = f"Unable to explain current trading risk: {exc}"
        return result_success(Intent.EXPLAIN_CURRENT_TRADING_RISK, body, data={"read_only": True})
