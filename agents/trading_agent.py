"""Trading Agent — dashboard, loop lifecycle, kill-switch (Sprint 3 / S3.4).

Extracted from ResearchAgent.  Trading intents previously fell through to
AgentId.RESEARCH via the catch-all in intent_routing.py; they now route
explicitly to AgentId.TRADING.

All execution still goes through ActionRegistry.
"""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.TRADING

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Trading Agent",
    owns=(
        "trading loop lifecycle: start, stop (CONFIRMATION_REQUIRED)",
        "kill-switch: enable/disable (CONFIRMATION_REQUIRED)",
        "trading dashboard health monitoring",
        "live report display and position queries",
        "trading log search and error triage",
    ),
    runtime_modules=(
        "actions/trading_dashboard.py",
        "actions/trading_loop.py",
        "actions/trading_logs.py",
        "actions/trading_reports.py",
        "runtime/dashboard_health.py",
    ),
)


class TradingAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def dashboard_health(self) -> str:
        from actions.trading_dashboard import ShowDashboardHealthAction
        from core.types import CommandRequest, Intent
        result = ShowDashboardHealthAction().execute(
            CommandRequest(raw_text="show dashboard health", intent=Intent.SHOW_DASHBOARD_HEALTH)
        )
        return result.summary or ""

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry
        return ActionRegistry().execute(request)

    def health_check(self) -> bool:
        """Returns True when the trading dashboard URL is configured."""
        try:
            import config
            return bool(getattr(config, "TRADING_DASHBOARD_URL", ""))
        except Exception:
            return False


_trading_agent: TradingAgent | None = None


def get_trading_agent() -> TradingAgent:
    global _trading_agent
    if _trading_agent is None:
        _trading_agent = TradingAgent()
    return _trading_agent
