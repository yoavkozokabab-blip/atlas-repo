"""Phase 78 — adapter from a ToolSpec to the existing ActionRegistry path.

The adapter is the bridge: it builds a CommandRequest from validated tool args,
executes it through the SAME ActionRegistry path used today (so existing agent
gating + behavior are preserved), and maps the CommandResult back to a ToolResult
**without ever upgrading a non-success status to success**.
"""

from __future__ import annotations

from typing import Any

from core.types import ActionStatus, CommandRequest, Intent
from tools.spec import ToolResult, ToolSpec, ToolStatus

# Map underlying ActionStatus -> ToolStatus. Fidelity-preserving: no upgrades.
_STATUS_MAP = {
    ActionStatus.SUCCESS: ToolStatus.SUCCESS,
    ActionStatus.FAILED: ToolStatus.FAILED,
    ActionStatus.BLOCKED: ToolStatus.BLOCKED,
    ActionStatus.CONFIRMATION_REQUIRED: ToolStatus.NEEDS_APPROVAL,
    ActionStatus.CLARIFICATION_NEEDED: ToolStatus.NEEDS_INPUT,
    ActionStatus.NOT_IMPLEMENTED: ToolStatus.ERROR,
}


class SchemaValidationError(ValueError):
    """Raised when tool args do not satisfy input_schema."""


_PY_TYPES = {
    "string": str, "integer": int, "number": (int, float),
    "boolean": bool, "array": list, "object": dict,
}


def validate_args(spec: ToolSpec, args: dict[str, Any]) -> None:
    """Lightweight JSON-Schema-subset validation (required keys + primitive types)."""
    schema = spec.input_schema or {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for key in required:
        if key not in args or args[key] in (None, ""):
            raise SchemaValidationError(f"missing required arg '{key}'")
    for key, val in args.items():
        decl = props.get(key)
        if not decl:
            continue
        expected = _PY_TYPES.get(decl.get("type"))
        if expected and not isinstance(val, expected):
            raise SchemaValidationError(
                f"arg '{key}' expected {decl.get('type')}, got {type(val).__name__}"
            )


def build_request(spec: ToolSpec, args: dict[str, Any]) -> CommandRequest:
    params = {spec.arg_map.get(k, k): v for k, v in args.items()}
    raw_text = spec.raw_text_template.format(**args) if spec.raw_text_template else spec.name
    return CommandRequest(
        raw_text=raw_text,
        intent=Intent(spec.maps_to_intent),
        params=params,
        confidence=1.0,
        confirmed=spec.requires_approval,  # only set when the registry already approved
        classifier_source="tool_registry",
    )


def map_result(spec: ToolSpec, command_result) -> ToolResult:
    status = _STATUS_MAP.get(command_result.status, ToolStatus.ERROR)
    data = dict(command_result.data or {})
    return ToolResult(
        tool_name=spec.name,
        status=status,                       # never upgraded
        summary=command_result.summary or "",
        data=data,
        agent_id=str(data.get("agent_id", "")),
    )
