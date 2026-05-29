"""Phase 78 — LLM-first Tool Registry (additive layer).

Typed, safety-classed tools that dispatch through the existing ActionRegistry
path. Central safety enforcement; no mock success; LLM routing disabled this
phase (the keyword classifier and ActionRegistry remain authoritative).
"""

from __future__ import annotations

from tools.flags import (
    llm_tool_router_enabled,
    llm_tool_router_readonly_only,
    llm_tool_router_shadow,
    tool_registry_enabled,
    tool_registry_shadow_compare,
)
from tools.registry import ToolRegistry, ToolRegistrationError, get_tool_registry
from tools.spec import (
    SafetyClass,
    SideEffect,
    ToolResult,
    ToolSpec,
    ToolStatus,
    Verification,
)

__all__ = [
    "tool_registry_enabled",
    "llm_tool_router_enabled",
    "llm_tool_router_shadow",
    "llm_tool_router_readonly_only",
    "tool_registry_shadow_compare",
    "ToolRegistry", "ToolRegistrationError", "get_tool_registry",
    "ToolSpec", "ToolResult", "ToolStatus", "SafetyClass", "SideEffect", "Verification",
]
