"""Predefined workflow registry (code-only)."""

from __future__ import annotations

from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS
from workflows.models import WorkflowDefinition
from workflows.system_workflows import (
    code_risk_review,
    jarvis_self_check,
    screen_error_check,
)
from workflows.trading_workflows import trading_health_check


class WorkflowRegistryError(Exception):
    pass


def _bootstrap() -> dict[str, WorkflowDefinition]:
    workflows = [
        trading_health_check(),
        screen_error_check(),
        code_risk_review(),
        jarvis_self_check(),
    ]
    reg: dict[str, WorkflowDefinition] = {}
    for wf in workflows:
        _validate_workflow(wf)
        reg[wf.name] = wf
    return reg


def _validate_workflow(wf: WorkflowDefinition) -> None:
    if not wf.steps:
        raise WorkflowRegistryError(f"Workflow '{wf.name}' has no steps.")
    for step in wf.steps:
        if step.intent not in IMPLEMENTED_INTENTS:
            raise WorkflowRegistryError(
                f"Workflow '{wf.name}' step '{step.intent}' is not implemented."
            )
        if step.intent in CONFIRMATION_REQUIRED_INTENTS:
            raise WorkflowRegistryError(
                f"Workflow '{wf.name}' cannot include confirm-required intent '{step.intent}'."
            )


_REGISTRY: dict[str, WorkflowDefinition] | None = None


def get_workflow_registry() -> dict[str, WorkflowDefinition]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _bootstrap()
    return _REGISTRY


def reset_workflow_registry() -> None:
    global _REGISTRY
    _REGISTRY = None


def list_workflow_names() -> list[str]:
    return sorted(get_workflow_registry().keys())


def get_workflow(name: str) -> WorkflowDefinition | None:
    return get_workflow_registry().get(name.strip().lower())


def resolve_workflow_alias(text: str) -> str | None:
    """Map alias phrase to workflow name."""
    norm = text.strip().lower()
    for wf in get_workflow_registry().values():
        if norm == wf.name or norm in (a.lower() for a in wf.aliases):
            return wf.name
        for alias in wf.aliases:
            if alias.lower() in norm or norm in alias.lower():
                return wf.name
    return None
