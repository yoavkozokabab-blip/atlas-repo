"""Coding Agent — project analysis, debugging, patch generation (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.CODING

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Coding Agent",
    owns=(
        "supervised task agent (inspect/execute/report)",
        "code search",
        "patch proposals and apply (gated)",
        "error explanation",
        "failing test discovery",
        "engineering execution helpers",
    ),
    runtime_modules=(
        "task_agent/",
        "actions/task_actions.py",
        "actions/code_search.py",
        "actions/productivity_actions.py",
        "investigation/patch_simulation.py",
        "assistant/engineering_execution.py",
        "phase45_investigation.py",
    ),
)


class CodingAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def active_task(self):
        from task_agent import get_active_task

        return get_active_task()

    def explain_latest_error(self) -> str:
        from phase45_investigation import explain_latest_error

        return explain_latest_error()

    def hunt_bugs(self) -> str:
        from phase45_investigation import hunt_algorithm_bugs

        return hunt_algorithm_bugs()

    def find_failing_tests(self) -> CommandResult:
        from core.types import CommandRequest, Intent

        return self.execute_via_registry(
            CommandRequest(raw_text="show failing tests", intent=Intent.SHOW_FAILING_TESTS)
        )

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_coding_agent: CodingAgent | None = None


def get_coding_agent() -> CodingAgent:
    global _coding_agent
    if _coding_agent is None:
        _coding_agent = CodingAgent()
    return _coding_agent
