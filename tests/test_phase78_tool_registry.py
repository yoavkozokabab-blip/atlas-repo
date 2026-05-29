"""Phase 78 — Tool Registry tests (deterministic; no live network/browser).

Proves: catalog integrity, central safety invariants, denylist rejection, schema
validation, adapter fidelity (no fake success), mapped-handler existence, audit
writes, startup validation, and that production routing is unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.types import ActionStatus, CommandResult, Intent
from tools import audit
from tools.adapters import SchemaValidationError, validate_args
from tools.catalog import build_default_tool_registry, default_specs
from tools.registry import ToolRegistry, ToolRegistrationError
from tools.spec import (
    AuthKind, CostHint, LatencyHint, SafetyClass, SideEffect,
    ToolSpec, ToolStatus, Verification,
)


# --- a deterministic fake ActionRegistry ----------------------------------

class FakeActionRegistry:
    def __init__(self, *, status_map=None, missing=()):
        self.status_map = status_map or {}
        self.missing = set(missing)
        self.calls = []

    def has(self, intent: str) -> bool:
        return intent not in self.missing

    def execute(self, request):
        self.calls.append(request)
        status = self.status_map.get(request.intent.value, ActionStatus.SUCCESS)
        data = {"agent_id": "executive"}
        return CommandResult(intent=request.intent, status=status,
                             summary=f"ran {request.intent.value}", data=data)


def _spec(name="x.tool", intent="show_capabilities", sc=SafetyClass.READ_ONLY,
          se=SideEffect.NONE, verify=(Verification.RESULT_SUCCESS,), args=None, required=None):
    props = {a: {"type": "string"} for a in (args or [])}
    return ToolSpec(
        name=name, version=1, description="t",
        input_schema={"properties": props, "required": list(required or [])},
        output_schema={}, safety_class=sc, side_effects=se, idempotent=True,
        verification=tuple(verify), maps_to_intent=intent,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    audit.reset_for_tests()
    yield
    audit.reset_for_tests()


# ---------------------------------------------------------------------------
# 1. Catalog integrity
# ---------------------------------------------------------------------------

def test_catalog_integrity():
    from actions.registry import ActionRegistry
    from config import IMPLEMENTED_INTENTS

    reg = ToolRegistry(action_registry=ActionRegistry())
    for spec in default_specs():
        reg.register(spec)

    specs = reg.all()
    assert len(specs) == 40
    assert len(reg.names()) == 40                       # unique names
    assert all(s.safety_class in (SafetyClass.READ_ONLY, SafetyClass.REVERSIBLE) for s in specs)
    # 39 READ_ONLY + exactly 1 approval-gated REVERSIBLE (research.run); 0 FORBIDDEN.
    assert sum(s.safety_class == SafetyClass.REVERSIBLE for s in specs) == 1
    assert sum(s.safety_class == SafetyClass.READ_ONLY for s in specs) == 39
    assert all(s.maps_to_intent in IMPLEMENTED_INTENTS for s in specs)
    counts = reg.by_safety_class()
    assert counts.get("irreversible_forbidden", 0) == 0


# ---------------------------------------------------------------------------
# 2. Safety invariants (central)
# ---------------------------------------------------------------------------

def test_forbidden_tool_cannot_register():
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(sc=SafetyClass.IRREVERSIBLE_FORBIDDEN))


def test_irreversible_external_cannot_register():
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(se=SideEffect.EXTERNAL_IRREVERSIBLE))


def test_malformed_name_rejected():
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(name="NoNamespace"))


def test_duplicate_name_rejected():
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    reg.register(_spec(name="a.one"))
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(name="a.one"))


# ---------------------------------------------------------------------------
# 3. Denylist rejection (no mock-success handler may back a tool)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("intent", ["find_information_about", "extract_key_facts_from_this_page"])
def test_mock_success_handlers_denylisted(intent):
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(name="web.bad", intent=intent))


# ---------------------------------------------------------------------------
# 4. Mapped handler must exist
# ---------------------------------------------------------------------------

def test_missing_handler_rejected():
    reg = ToolRegistry(action_registry=FakeActionRegistry(missing={"show_capabilities"}))
    with pytest.raises(ToolRegistrationError):
        reg.register(_spec(name="x.cap", intent="show_capabilities"))


# ---------------------------------------------------------------------------
# 5. Schema validation
# ---------------------------------------------------------------------------

def test_schema_validation_blocks_bad_args_without_executing():
    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="code.find", intent="find_function", args=["name"], required=["name"]))
    res = reg.invoke("code.find", {})  # missing required 'name'
    assert res.status == ToolStatus.ERROR
    assert res.reason == "invalid_args"
    assert fake.calls == []            # never executed


def test_validate_args_typecheck():
    spec = _spec(args=["n"], required=["n"])
    with pytest.raises(SchemaValidationError):
        validate_args(spec, {"n": 123})  # expected string


# ---------------------------------------------------------------------------
# 6. Adapter fidelity — no fake success
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action_status,tool_status", [
    (ActionStatus.SUCCESS, ToolStatus.SUCCESS),
    (ActionStatus.FAILED, ToolStatus.FAILED),
    (ActionStatus.BLOCKED, ToolStatus.BLOCKED),
    (ActionStatus.NOT_IMPLEMENTED, ToolStatus.ERROR),
    (ActionStatus.CLARIFICATION_NEEDED, ToolStatus.NEEDS_INPUT),
])
def test_status_never_upgraded(action_status, tool_status):
    fake = FakeActionRegistry(status_map={"show_capabilities": action_status})
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="a.cap", intent="show_capabilities"))
    res = reg.invoke("a.cap", {})
    assert res.status == tool_status
    if tool_status != ToolStatus.SUCCESS:
        assert res.verified is False


def test_failed_underlying_is_not_verified():
    fake = FakeActionRegistry(status_map={"show_system_health": ActionStatus.FAILED})
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="system.health", intent="show_system_health"))
    res = reg.invoke("system.health", {})
    assert res.status == ToolStatus.FAILED and res.verified is False


def test_provider_real_verification_rejects_mock_markers():
    # Underlying SUCCESS but data signals unavailable/mock -> verified False (defense in depth).
    class MockyRegistry(FakeActionRegistry):
        def execute(self, request):
            self.calls.append(request)
            return CommandResult(intent=request.intent, status=ActionStatus.SUCCESS,
                                 summary="MOCK MODE | NO REAL EXTERNAL ACCESS",
                                 data={"final_status": "blocked_unavailable"})
    reg = ToolRegistry(action_registry=MockyRegistry())
    reg.register(_spec(name="research.run", intent="run_tool_task",
                       sc=SafetyClass.REVERSIBLE, se=SideEffect.EXTERNAL_REVERSIBLE,
                       verify=(Verification.PROVIDER_REAL,)))
    res = reg.invoke("research.run", {}, allowed_classes=frozenset({SafetyClass.REVERSIBLE}), approved=True)
    assert res.verified is False  # mock/unavailable never verified as real


# ---------------------------------------------------------------------------
# 7. Central safety gate
# ---------------------------------------------------------------------------

def test_reversible_requires_approval():
    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="research.run", intent="run_tool_task",
                       sc=SafetyClass.REVERSIBLE, se=SideEffect.EXTERNAL_REVERSIBLE))
    # allowed class but not approved -> NEEDS_APPROVAL, never executed
    res = reg.invoke("research.run", {}, allowed_classes=frozenset({SafetyClass.REVERSIBLE}))
    assert res.status == ToolStatus.NEEDS_APPROVAL
    assert fake.calls == []


def test_safety_class_not_allowed_is_blocked():
    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="research.run", intent="run_tool_task",
                       sc=SafetyClass.REVERSIBLE, se=SideEffect.EXTERNAL_REVERSIBLE))
    res = reg.invoke("research.run", {})  # default allowed = READ_ONLY only
    assert res.status == ToolStatus.BLOCKED
    assert fake.calls == []


# ---------------------------------------------------------------------------
# 8. Audit writes
# ---------------------------------------------------------------------------

def test_audit_written_on_invoke(tmp_path):
    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    reg.register(_spec(name="a.cap", intent="show_capabilities"))
    reg.invoke("a.cap", {})
    audit_file = Path(tmp_path) / "tool_registry_audit.jsonl"
    rows = [json.loads(l) for l in audit_file.read_text().splitlines() if l.strip()]
    assert any(r["event"] == "invoke" and r["tool"] == "a.cap" for r in rows)


# ---------------------------------------------------------------------------
# 9. Startup validation
# ---------------------------------------------------------------------------

def test_validate_tool_catalog_clean():
    from core.startup_validation import validate_tool_catalog
    assert validate_tool_catalog() == []


# ---------------------------------------------------------------------------
# 10. Production routing unchanged
# ---------------------------------------------------------------------------

def test_llm_router_flag_off_by_default():
    from tools.flags import llm_tool_router_enabled
    assert llm_tool_router_enabled() is False


def test_classifier_and_router_unchanged():
    from brain.intent_classifier import classify
    from brain.router import CommandRouter
    # classifier still routes a known phrase to its intent (no tool interception)
    assert classify("show capabilities").intent == Intent.SHOW_CAPABILITIES
    # router still executes via the existing path
    result = CommandRouter().route("show capabilities")
    assert result.status == ActionStatus.SUCCESS


def test_building_catalog_does_not_mutate_action_registry():
    from actions.registry import ActionRegistry
    before = len(ActionRegistry()._actions)
    build_default_tool_registry(action_registry=ActionRegistry())
    after = len(ActionRegistry()._actions)
    assert before == after
