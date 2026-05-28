"""Executive Agent — request routing, delegation, aggregation (Phase 70 facade)."""

from __future__ import annotations

import time
from typing import Any

from agents.base import AgentCapability, AgentDelegation, AgentId
from agents.intent_routing import agent_for_intent
from agents.conversation_agent import get_conversation_agent
from agents.memory_agent import get_memory_agent
from agents.operator_agent import get_operator_agent
from agents.research_agent import get_research_agent
from agents.coding_agent import get_coding_agent
from agents.planning_agent import get_planning_agent
from core.types import CommandRequest, CommandResult, Intent

_AGENT_ID = AgentId.EXECUTIVE

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Executive Agent",
    owns=(
        "user request intake",
        "intent classification orchestration",
        "agent selection",
        "delegation to ActionRegistry",
        "result aggregation",
        "system/meta commands",
    ),
    runtime_modules=(
        "brain/router.py",
        "brain/intent_classifier.py",
        "actions/registry.py",
        "core/security.py",
        "core/confirmation.py",
        "core/app.py",
    ),
)

_AGENT_REGISTRY: dict[AgentId, Any] | None = None


def _agents() -> dict[AgentId, Any]:
    global _AGENT_REGISTRY
    if _AGENT_REGISTRY is None:
        _AGENT_REGISTRY = {
            AgentId.EXECUTIVE: None,
            AgentId.CONVERSATION: get_conversation_agent(),
            AgentId.MEMORY: get_memory_agent(),
            AgentId.OPERATOR: get_operator_agent(),
            AgentId.RESEARCH: get_research_agent(),
            AgentId.CODING: get_coding_agent(),
            AgentId.PLANNING: get_planning_agent(),
        }
    return _AGENT_REGISTRY


class ExecutiveAgent:
    """
    Formalizes orchestration already performed by CommandRouter.

    Does not replace router/registry — wraps them for agent architecture clarity.
    """

    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def receive_request(self, text: str, *, input_mode: str = "text") -> CommandRequest:
        from brain.intent_classifier import classify

        return classify(text)

    def select_agent(self, intent: Intent | str) -> AgentId:
        return agent_for_intent(intent)

    def delegate(
        self,
        request: CommandRequest,
        *,
        registry: Any | None = None,
    ) -> AgentDelegation:
        """
        Execute via existing ActionRegistry (same path as CommandRouter._process).
        """
        agent_id = self.select_agent(request.intent)
        start = time.perf_counter()
        if registry is None:
            from actions.registry import ActionRegistry

            registry = ActionRegistry()
        result = registry.execute(request)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return AgentDelegation(
            agent_id=agent_id,
            request=request,
            result=result,
            latency_ms=latency_ms,
            metadata={"intent": request.intent.value},
        )

    def route_text(self, text: str, *, input_mode: str = "text") -> CommandResult:
        """
        Full path through CommandRouter (preserves confirm/alias/follow-up behavior).
        """
        from brain.router import CommandRouter

        return CommandRouter().route(text, input_mode=input_mode)

    def aggregate(self, delegations: list[AgentDelegation]) -> str:
        if not delegations:
            return "No agent results."
        lines = [f"Executive summary ({len(delegations)} step(s)):"]
        for d in delegations:
            status = d.result.status.value
            lines.append(f"  - [{d.agent_id.value}] {d.request.intent.value}: {status}")
        return "\n".join(lines)

    def get_agent(self, agent_id: AgentId) -> Any:
        return _agents().get(agent_id)

    def capability_catalog(self) -> list[AgentCapability]:
        return [
            _CAPABILITY,
            get_conversation_agent().capability,
            get_memory_agent().capability,
            get_operator_agent().capability,
            get_research_agent().capability,
            get_coding_agent().capability,
            get_planning_agent().capability,
        ]


_executive: ExecutiveAgent | None = None


def get_executive_agent() -> ExecutiveAgent:
    global _executive
    if _executive is None:
        _executive = ExecutiveAgent()
    return _executive
