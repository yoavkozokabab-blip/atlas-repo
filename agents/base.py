"""Agent architecture primitives (Phase 70) — delegation only, no new capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.types import CommandRequest, CommandResult


class AgentId(str, Enum):
    EXECUTIVE = "executive"
    CONVERSATION = "conversation"
    MEMORY = "memory"
    OPERATOR = "operator"
    RESEARCH = "research"
    CODING = "coding"
    PLANNING = "planning"


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
