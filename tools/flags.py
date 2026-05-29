"""Phase 78 — Tool Registry feature flags (env-driven, documented defaults).

These are read from the environment so the additive Tool Registry can ship
without entangling the shared, in-flight config.py. They can be promoted into
config.py later once the working tree settles.

Defaults (per the Phase 78 plan):
  TOOL_REGISTRY_ENABLED        = true    build + validate the catalog at startup
  LLM_TOOL_ROUTER_ENABLED      = false   Phase 79 — shadow/canary (default off)
  LLM_TOOL_ROUTER_SHADOW       = false   Stage 1 — log only, never execute
  LLM_TOOL_ROUTER_READONLY_ONLY = true   Stage 2+ — REVERSIBLE tools → clarify
  TOOL_REGISTRY_SHADOW_COMPARE = false   dev-only parity telemetry; no user effect
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in _TRUE


def tool_registry_enabled() -> bool:
    return _flag("TOOL_REGISTRY_ENABLED", True)


def llm_tool_router_enabled() -> bool:
    return _flag("LLM_TOOL_ROUTER_ENABLED", False)


def llm_tool_router_shadow() -> bool:
    return _flag("LLM_TOOL_ROUTER_SHADOW", False)


def llm_tool_router_readonly_only() -> bool:
    return _flag("LLM_TOOL_ROUTER_READONLY_ONLY", True)


def tool_registry_shadow_compare() -> bool:
    return _flag("TOOL_REGISTRY_SHADOW_COMPARE", False)
