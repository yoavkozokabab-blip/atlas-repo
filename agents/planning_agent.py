"""Planning Agent — tasks, goals, schedules (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.PLANNING

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Planning Agent",
    owns=(
        "task plans and step execution",
        "task queue",
        "experiment planning",
        "workflows",
        "assistant planning",
        "investigation scheduler",
        "proactive suggestions",
        "workspace bootstraps",
    ),
    runtime_modules=(
        "task_agent/planner.py",
        "task_agent/queue.py",
        "task_agent/experiment_planner.py",
        "assistant/plan_rules.py",
        "assistant/investigation_scheduler.py",
        "assistant/proactive_assistant.py",
        "workflows/registry.py",
        "workflows/runner.py",
        "actions/task_actions.py",
        "actions/assistant_actions.py",
        "actions/workflow_actions.py",
    ),
)


class PlanningAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def create_plan(self, objective: str):
        from task_agent.planner import create_plan_from_objective

        return create_plan_from_objective(objective)

    def format_queue(self) -> str:
        from task_agent.queue import format_queue

        return format_queue()

    def build_experiment_plan(self) -> str:
        from task_agent.experiment_planner import build_experiment_plan

        return build_experiment_plan()

    def run_workflow(self, workflow_name: str):
        from workflows.runner import WorkflowRunner

        return WorkflowRunner().run(workflow_name)

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_planning_agent: PlanningAgent | None = None


def get_planning_agent() -> PlanningAgent:
    global _planning_agent
    if _planning_agent is None:
        _planning_agent = PlanningAgent()
    return _planning_agent
