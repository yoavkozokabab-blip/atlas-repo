"""Agent runtime wiring — execution path ownership and health gating (Sprint 3.1).

Every command executed via ``ActionRegistry.execute`` resolves an owning agent,
records runtime metadata on the result, and blocks unsafe work when the owner
(or a dependency) is unhealthy.  Handlers are unchanged; this layer wraps them.
"""

from __future__ import annotations

from dataclasses import dataclass

from agents.base import AgentId
from agents.intent_routing import agent_for_intent
from agents.registry import AgentRegistry, build_default_registry, get_agent_registry
from core.logger import setup_logger
from core.types import CommandRequest, CommandResult, Intent

logger = setup_logger("jarvis.agents.runtime_wiring")

ROUTING_SOURCE = "intent_routing.agent_for_intent"

# Agents whose intents are blocked when health_check() is False (unless diagnostic).
_HEALTH_GATED_AGENTS: frozenset[AgentId] = frozenset({
    AgentId.BROWSER,
    AgentId.DESKTOP,
    AgentId.TRADING,
    AgentId.CODING,
})

_HEALTH_DIAGNOSTIC_SUFFIXES: tuple[str, ...] = (
    "_health",
    "_debug",
    "_status",
)


@dataclass(frozen=True)
class AgentExecutionContext:
    """Resolved agent ownership for one command execution."""

    agent_id: AgentId
    agent_health: bool
    routing_source: str


def ensure_agent_registry() -> AgentRegistry:
    """Return the process registry, bootstrapping defaults when empty."""
    reg = get_agent_registry()
    if not reg.all_ids():
        build_default_registry()
    return reg


def resolve_execution_context(request: CommandRequest) -> AgentExecutionContext:
    """Resolve owning agent and health for a command (before handler runs)."""
    agent_id = agent_for_intent(request.intent)
    registry = ensure_agent_registry()
    healthy = evaluate_agent_health(agent_id, registry)
    return AgentExecutionContext(
        agent_id=agent_id,
        agent_health=healthy,
        routing_source=ROUTING_SOURCE,
    )


def evaluate_agent_health(agent_id: AgentId, registry: AgentRegistry) -> bool:
    """True when the agent and all depends_on agents pass health_check()."""
    reg = registry.get(agent_id)
    if reg is None:
        return True
    try:
        if not bool(reg.health_check()):
            return False
    except Exception as exc:
        logger.warning(
            "agent health_check raised for %s: %s",
            agent_id.value,
            exc,
        )
        return False
    for dep_id in reg.depends_on:
        if not evaluate_agent_health(dep_id, registry):
            return False
    return True


def is_health_diagnostic_intent(intent: Intent) -> bool:
    """Read-only health/status intents may run when the owner agent is degraded."""
    value = intent.value
    return any(value.endswith(suffix) for suffix in _HEALTH_DIAGNOSTIC_SUFFIXES)


def requires_healthy_owner(agent_id: AgentId, intent: Intent) -> bool:
    if agent_id not in _HEALTH_GATED_AGENTS:
        return False
    return not is_health_diagnostic_intent(intent)


def should_block_unhealthy_execution(
    agent_id: AgentId,
    intent: Intent,
    agent_health: bool,
) -> tuple[bool, str]:
    if agent_health or not requires_healthy_owner(agent_id, intent):
        return False, ""
    return (
        True,
        f"{agent_id.value} agent is unhealthy; refusing unsafe execution.",
    )


def attach_agent_runtime_metadata(
    result: CommandResult,
    ctx: AgentExecutionContext,
) -> CommandResult:
    data = dict(result.data)
    data["agent_id"] = ctx.agent_id.value
    data["agent_health"] = ctx.agent_health
    data["routing_source"] = ctx.routing_source
    return result.model_copy(update={"data": data})


def block_unhealthy_result(
    request: CommandRequest,
    ctx: AgentExecutionContext,
    reason: str,
) -> CommandResult:
    from core.results import result_failed

    return result_failed(
        request.intent,
        reason,
        error=reason,
        data={
            "agent_id": ctx.agent_id.value,
            "agent_health": False,
            "routing_source": ctx.routing_source,
            "blocked_by_agent_health": True,
        },
    )
