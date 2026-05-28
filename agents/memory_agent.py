"""Memory Agent — storage, retrieval, ranking, repair (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.MEMORY

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Memory Agent",
    owns=(
        "personal memory store",
        "semantic search",
        "memory graph",
        "project indexing",
        "session/task memory",
        "preferences and aliases",
        "memory repair",
    ),
    runtime_modules=(
        "memory/store.py",
        "memory/search.py",
        "memory/semantic_runtime.py",
        "memory/graph.py",
        "memory/repair.py",
        "memory/project_indexer.py",
        "memory/session_memory.py",
        "brain/memory.py",
        "brain/aliases.py",
        "actions/memory_actions.py",
        "actions/knowledge_actions.py",
    ),
)


class MemoryAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def store(self):
        from memory.store import get_personal_memory

        return get_personal_memory()

    def remember(self, text: str, *, category: str = "session", tags: list[str] | None = None) -> str:
        entry = self.store().remember(text, category=category, tags=tags or [])
        return entry.entry_id

    def search(self, query: str, limit: int = 10) -> list:
        return self.store().search_memory(query)[:limit]

    def semantic_search(self, query: str, limit: int = 5) -> list:
        return self.store().semantic_search(query, limit=limit)

    def repair(self) -> str:
        from memory.repair import repair_memory_store

        return repair_memory_store()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_memory_agent: MemoryAgent | None = None


def get_memory_agent() -> MemoryAgent:
    global _memory_agent
    if _memory_agent is None:
        _memory_agent = MemoryAgent()
    return _memory_agent
