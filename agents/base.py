"""Agent architecture primitives (Phase 70) — delegation only, no new capabilities.

Sprint 3 additions:
- BROWSER      extracted from OPERATOR; owns browser runtime, DOM read, web search
- DESKTOP      extracted from OPERATOR; owns window control, screen capture, apps
- TRADING      extracted from RESEARCH; owns trading loop, dashboard, kill-switch
- HEALTH_MONITOR  new; owns system health, storage checks, dependency validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.types import CommandRequest, CommandResult


class AgentId(str, Enum):
    EXECUTIVE = "executive"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    OPERATOR = "operator"       # legacy shim — browser + desktop now split below
    RESEARCH = "research"
    CODING = "coding"
    PLANNING = "planning"
    # --- Sprint 3 additions ---
    BROWSER = "browser"
    DESKTOP = "desktop"
    TRADING = "trading"
    HEALTH_MONITOR = "health_monitor"


@dataclass(frozen=True)
class AgentCapability:
    """Documents what an agent owns (runtime paths, not new features)."""

    agent_id: AgentId
    name: str
    owns: tuple[str, ...]
    runtime_modules: tuple[str, ...]


@dataclass
class AgentDelegation:
    """Result of executive delegation through existing ActionRegistry."""

    agent_id: AgentId
    request: CommandRequest
    result: CommandResult
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        from core.types import ActionStatus

        return self.result.status == ActionStatus.SUCCESS
