"""Agent Registry — formal registration of all agents (Sprint 3 / S3.1).

Provides:
- AgentRegistration dataclass (agent + health_check + intent_prefixes + depends_on)
- AgentRegistry singleton that holds all registrations
- validate_registry() — called at startup to assert every agent is healthy

Ownership and health registration.  Command execution goes through
brain/router.py → actions/registry.py, which applies agents/runtime_wiring.py
for agent resolution, health gating, and per-result metadata.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Any

from agents.base import AgentId
from core.logger import setup_logger

logger = setup_logger("jarvis.agents.registry")


@dataclass
class AgentRegistration:
    """
    Metadata record for one agent.

    health_check: callable that returns True when the agent is operational.
    intent_prefixes: tuple of intent value prefixes this agent owns (for docs only —
                     routing is done by agents/intent_routing.py).
    depends_on: AgentIds that must be healthy before this agent can function.
    """
    agent_id: AgentId
    agent: Any
    health_check: Callable[[], bool]
    intent_prefixes: tuple[str, ...] = field(default_factory=tuple)
    depends_on: tuple[AgentId, ...] = field(default_factory=tuple)


class AgentRegistry:
    """Holds all agent registrations and validates their health at startup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._registrations: dict[AgentId, AgentRegistration] = {}

    def register(self, registration: AgentRegistration) -> None:
        with self._lock:
            self._registrations[registration.agent_id] = registration
        logger.debug("AgentRegistry: registered '%s'", registration.agent_id.value)

    def get(self, agent_id: AgentId) -> AgentRegistration | None:
        with self._lock:
            return self._registrations.get(agent_id)

    def all_ids(self) -> list[AgentId]:
        with self._lock:
            return list(self._registrations.keys())

    def validate(self) -> list[str]:
        """
        Run every registered agent's health_check().
        Returns list of error strings (empty = all healthy).
        Logs warnings for unhealthy agents; does not abort startup.
        """
        errors: list[str] = []
        with self._lock:
            snapshot = dict(self._registrations)

        for agent_id, reg in snapshot.items():
            try:
                healthy = reg.health_check()
            except Exception as exc:
                healthy = False
                logger.warning(
                    "AgentRegistry: health_check for '%s' raised: %s",
                    agent_id.value, exc,
                )
            if not healthy:
                msg = f"Agent '{agent_id.value}' health_check() returned False"
                errors.append(msg)
                logger.warning("AgentRegistry: %s", msg)
            else:
                logger.debug("AgentRegistry: '%s' healthy", agent_id.value)

        if not errors:
            logger.info(
                "AgentRegistry: all %d agents healthy", len(snapshot)
            )
        else:
            logger.warning(
                "AgentRegistry: %d agent(s) unhealthy: %s",
                len(errors),
                [e.split("'")[1] for e in errors],
            )
        return errors

    def snapshot(self) -> dict[str, bool]:
        """Return {agent_id.value: is_healthy} for all registered agents."""
        result: dict[str, bool] = {}
        with self._lock:
            snapshot = dict(self._registrations)
        for agent_id, reg in snapshot.items():
            try:
                result[agent_id.value] = bool(reg.health_check())
            except Exception:
                result[agent_id.value] = False
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: AgentRegistry | None = None
_registry_lock = threading.Lock()


def get_agent_registry() -> AgentRegistry:
    """Return the process-wide AgentRegistry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = AgentRegistry()
    return _registry


# ---------------------------------------------------------------------------
# Bootstrap helper — build the full 11-agent registry
# (Calendar and Email agents are in Sprint 6 and are not registered yet)
# ---------------------------------------------------------------------------

def build_default_registry() -> AgentRegistry:
    """
    Populate the AgentRegistry with all current agents and return it.
    Called once at startup from core/runtime_bootstrap.py.
    """
    reg = get_agent_registry()

    from agents.conversation_agent import get_conversation_agent
    from agents.memory_agent       import get_memory_agent
    from agents.operator_agent     import get_operator_agent
    from agents.research_agent     import get_research_agent
    from agents.coding_agent       import get_coding_agent
    from agents.planning_agent     import get_planning_agent
    from agents.browser_agent      import get_browser_agent
    from agents.desktop_agent      import get_desktop_agent
    from agents.trading_agent      import get_trading_agent
    from agents.health_monitor_agent import get_health_monitor_agent

    # ── Commander / Executive ───────────────────────────────────────────────
    # health_check: ActionRegistry and security module must be importable
    def _executive_hc() -> bool:
        try:
            from core.security import validate_intent  # noqa: F401
            from actions.registry import ActionRegistry  # noqa: F401
            return True
        except Exception:
            return False

    from agents.executive_agent import get_executive_agent
    reg.register(AgentRegistration(
        agent_id=AgentId.EXECUTIVE,
        agent=get_executive_agent(),
        health_check=_executive_hc,
        intent_prefixes=("unknown", "clarify", "show_capabilities", "show_jarvis_status"),
        depends_on=(),
    ))

    # ── Voice / Conversation ────────────────────────────────────────────────
    def _voice_hc() -> bool:
        try:
            from voice.spoken_normalization import normalize_spoken_command  # noqa: F401
            return True
        except Exception:
            return False

    reg.register(AgentRegistration(
        agent_id=AgentId.CONVERSATION,
        agent=get_conversation_agent(),
        health_check=_voice_hc,
        intent_prefixes=("show_voice", "test_tts", "show_stt", "calibrate_voice",
                         "show_audio", "cancel_active_speech"),
        depends_on=(),
    ))

    # ── Memory ───────────────────────────────────────────────────────────────
    mem_agent = get_memory_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.MEMORY,
        agent=mem_agent,
        health_check=lambda: mem_agent.store()._load() is not None,
        intent_prefixes=("remember", "forget_memory", "search_memory", "show_memory",
                         "set_preference", "set_alias", "summarize_session"),
        depends_on=(),
    ))

    # ── Browser ──────────────────────────────────────────────────────────────
    browser_agent = get_browser_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.BROWSER,
        agent=browser_agent,
        health_check=browser_agent.health_check,
        intent_prefixes=("open_browser", "search_web", "find_information",
                         "summarize_this_page", "open_best_result", "what_tab"),
        depends_on=(),
    ))

    # ── Desktop ──────────────────────────────────────────────────────────────
    desktop_agent = get_desktop_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.DESKTOP,
        agent=desktop_agent,
        health_check=desktop_agent.health_check,
        intent_prefixes=("open_app", "focus_window", "describe_screen", "take_screenshot",
                         "what_is_on_my_screen", "click_button", "type_this"),
        depends_on=(),
    ))

    # ── Operator (legacy shim — keeps both browser + desktop for compatibility) ─
    op_agent = get_operator_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.OPERATOR,
        agent=op_agent,
        health_check=lambda: True,  # shim; browser + desktop each have real checks
        intent_prefixes=(),         # routing goes to BROWSER or DESKTOP now
        depends_on=(AgentId.BROWSER, AgentId.DESKTOP),
    ))

    # ── Research ─────────────────────────────────────────────────────────────
    research_agent = get_research_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.RESEARCH,
        agent=research_agent,
        health_check=lambda: True,  # investigation modules are always importable
        intent_prefixes=("investigate", "compare_live", "build_investigation",
                         "propose_investigation"),
        depends_on=(),
    ))

    # ── Trading ──────────────────────────────────────────────────────────────
    trading_agent = get_trading_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.TRADING,
        agent=trading_agent,
        health_check=trading_agent.health_check,
        intent_prefixes=("run_live", "open_trading_dashboard", "show_dashboard_health",
                         "enable_kill_switch", "disable_kill_switch", "show_open_positions",
                         "show_last_errors", "show_rejection_reasons", "search_trading"),
        depends_on=(),
    ))

    # ── Coding ───────────────────────────────────────────────────────────────
    coding_agent = get_coding_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.CODING,
        agent=coding_agent,
        health_check=lambda: coding_agent.active_task() is not None or True,
        intent_prefixes=("find_function", "find_class", "search_code",
                         "apply_task_patch", "explain_latest_error", "inspect_project"),
        depends_on=(),
    ))

    # ── Planning ─────────────────────────────────────────────────────────────
    planning_agent = get_planning_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.PLANNING,
        agent=planning_agent,
        health_check=lambda: True,  # task planner is always available
        intent_prefixes=("start_task", "run_task_step", "run_workflow",
                         "queue_task", "plan_experiments"),
        depends_on=(),
    ))

    # ── Health Monitor ───────────────────────────────────────────────────────
    hm_agent = get_health_monitor_agent()
    reg.register(AgentRegistration(
        agent_id=AgentId.HEALTH_MONITOR,
        agent=hm_agent,
        health_check=hm_agent.health_check,
        intent_prefixes=("show_system_health", "run_jarvis_health_check",
                         "show_watchdog_status"),
        depends_on=(),
    ))

    return reg


def validate_registry() -> list[str]:
    """Run validate() on the singleton registry. Called at startup."""
    return get_agent_registry().validate()
