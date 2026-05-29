"""Phase 78 — ToolSpec schema + result types for the LLM-first Tool Registry.

A ToolSpec is a frozen, declarative description of a capability. It does not
execute anything itself; an adapter (tools/adapters.py) invokes the underlying
existing handler through ActionRegistry. Safety is enforced centrally by the
registry (tools/registry.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyClass(str, Enum):
    READ_ONLY = "read_only"                 # no external irreversible effect; ungated
    REVERSIBLE = "reversible"               # approval-gated (Phase 95 semantics)
    IRREVERSIBLE_FORBIDDEN = "irreversible_forbidden"  # may NEVER be registered


class SideEffect(str, Enum):
    NONE = "none"
    LOCAL_WRITE = "local_write"             # memory/notes/report — reversible, ungated
    LOCAL_LAUNCH = "local_launch"           # open allowlisted app/site
    EXTERNAL_READ = "external_read"         # reads external state (screen, web page)
    EXTERNAL_REVERSIBLE = "external_reversible"
    EXTERNAL_IRREVERSIBLE = "external_irreversible"   # forbidden


class CostHint(str, Enum):
    FREE = "free"
    CHEAP = "cheap"
    NETWORK = "network"
    EXPENSIVE = "expensive"


class LatencyHint(str, Enum):
    INSTANT = "instant"
    FAST = "fast"
    SLOW = "slow"


class AuthKind(str, Enum):
    NONE = "none"
    CONNECTOR_TOKEN = "connector_token"


class Verification(str, Enum):
    RESULT_SUCCESS = "result_success"
    NON_EMPTY_SUMMARY = "non_empty_summary"
    PROVIDER_REAL = "provider_real"
    SCHEMA_VALID = "schema_valid"
    CROSS_SOURCE = "cross_source"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: int
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    safety_class: SafetyClass
    side_effects: SideEffect
    idempotent: bool
    verification: tuple[Verification, ...]
    maps_to_intent: str
    arg_map: dict[str, str] = field(default_factory=dict)
    raw_text_template: str = ""
    auth: AuthKind = AuthKind.NONE
    cost_hint: CostHint = CostHint.CHEAP
    latency_hint: LatencyHint = LatencyHint.FAST
    enabled: bool = True
    tags: tuple[str, ...] = ()

    @property
    def requires_approval(self) -> bool:
        # READ_ONLY -> no approval; REVERSIBLE -> approval; FORBIDDEN never runs.
        return self.safety_class == SafetyClass.REVERSIBLE


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"
    NEEDS_INPUT = "needs_input"
    ERROR = "error"


@dataclass
class ToolResult:
    tool_name: str
    status: ToolStatus
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    verification_reason: str = ""
    agent_id: str = ""
    reason: str = ""   # machine-readable reason for non-success (e.g. invalid_args)

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.SUCCESS
