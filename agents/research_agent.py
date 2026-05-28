"""Research Agent — search, comparison, summarization (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.RESEARCH

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Research Agent",
    owns=(
        "web research and summarization",
        "investigation graphs",
        "trading mismatch analysis",
        "email/calendar read-only summaries",
        "comparison reports",
        "hypothesis and evidence collection",
    ),
    runtime_modules=(
        "phase45_investigation.py",
        "investigation/",
        "assistant/investigation_graph.py",
        "assistant/hypothesis_engine.py",
        "task_agent/trading_deep_review.py",
        "providers/daily_summary_provider.py",
        "browser/runtime.py",
        "actions/phase45_actions.py",
    ),
)


class ResearchAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def inspect_project(self) -> str:
        from phase45_investigation import inspect_project

        return inspect_project()

    def compare_live_vs_backtest(self) -> str:
        from phase45_investigation import compare_live_vs_backtest

        return compare_live_vs_backtest()

    def summarize_inbox(self, count: int = 20) -> str:
        from reliability.integrations_health import summarize_my_inbox

        return summarize_my_inbox(count)

    def summarize_page(self) -> str:
        from browser.runtime import summarize_current_page

        return summarize_current_page()

    def compare_results(self) -> str:
        from browser.runtime import compare_latest_results

        return compare_latest_results()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_research_agent: ResearchAgent | None = None


def get_research_agent() -> ResearchAgent:
    global _research_agent
    if _research_agent is None:
        _research_agent = ResearchAgent()
    return _research_agent
