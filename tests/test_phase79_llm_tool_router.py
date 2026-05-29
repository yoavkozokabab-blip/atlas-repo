"""Phase 79 Stage 1 — Shadow LLM tool router (deterministic; fake llm_fn)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.types import CommandRequest, Intent
from tests.test_phase78_tool_registry import FakeActionRegistry
from tools.catalog import build_default_tool_registry, default_specs
from tools.registry import ToolRegistry, reset_for_tests as reset_tool_registry


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from brain import tool_router_audit
    from brain.llm_tool_router import reset_llm_tool_router_for_tests
    from tools import flags

    monkeypatch.setattr("config.DATA_DIR", tmp_path)
    tool_router_audit.reset_for_tests()
    reset_llm_tool_router_for_tests()
    reset_tool_registry()
    monkeypatch.setenv("LLM_TOOL_ROUTER_ENABLED", "false")
    monkeypatch.setenv("LLM_TOOL_ROUTER_SHADOW", "false")
    monkeypatch.delenv("LLM_TOOL_ROUTER_READONLY_ONLY", raising=False)
    yield
    reset_llm_tool_router_for_tests()
    reset_tool_registry()
    tool_router_audit.reset_for_tests()


def _enable_shadow(monkeypatch):
    monkeypatch.setenv("LLM_TOOL_ROUTER_ENABLED", "true")
    monkeypatch.setenv("LLM_TOOL_ROUTER_SHADOW", "true")


def _build_registry():
    reg = ToolRegistry(action_registry=FakeActionRegistry())
    for spec in default_specs():
        reg.register(spec)
    return reg


def _llm(raw: str):
    def _fn(_system: str, _user: str) -> str:
        return raw

    return _fn


def _audit_lines(tmp_path: Path) -> list[dict]:
    path = tmp_path / "llm_router_audit.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_flag_off_router_never_invoked(monkeypatch):
    from brain.llm_tool_router import get_router_invoke_count, shadow_route_miss

    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="xyzzy", intent=Intent.UNKNOWN, confidence=0.0)
    shadow_route_miss("xyzzy", rule_request=req, llm_fn=_llm('{"no_tool": true}'))
    assert get_router_invoke_count() == 0


def test_miss_only_invocation(monkeypatch):
    from brain.llm_tool_router import get_router_invoke_count, maybe_shadow_route_on_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)

    hit = CommandRequest(
        raw_text="show capabilities",
        intent=Intent.SHOW_CAPABILITIES,
        confidence=0.99,
    )
    maybe_shadow_route_on_miss("show capabilities", hit, llm_fn=_llm('{"tool_call": {"name": "x", "args": {}}}'))
    assert get_router_invoke_count() == 0

    miss = CommandRequest(raw_text="xyzzy", intent=Intent.UNKNOWN, confidence=0.0)
    maybe_shadow_route_on_miss("xyzzy", miss, llm_fn=_llm('{"no_tool": true}'))
    assert get_router_invoke_count() == 1


def test_malformed_llm_output_clarify(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="mystery task", intent=Intent.UNKNOWN, confidence=0.0)
    decision = route_miss("mystery task", rule_request=req, llm_fn=_llm("not json at all"))
    assert decision.outcome == "clarify"
    lines = _audit_lines(tmp_path)
    assert lines and lines[-1]["outcome"] == "clarify"


def test_hallucinated_tool_clarify(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="do something odd", intent=Intent.UNKNOWN, confidence=0.0)
    raw = json.dumps({"tool_call": {"name": "fake.tool", "args": {}}})
    decision = route_miss("do something odd", rule_request=req, llm_fn=_llm(raw))
    assert decision.outcome == "clarify"
    assert "hallucinated" in decision.fallback_reason


def test_forbidden_request_refuse(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="buy me a laptop", intent=Intent.UNKNOWN, confidence=0.0)
    decision = route_miss(
        "buy me a laptop",
        rule_request=req,
        llm_fn=_llm(json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})),
    )
    assert decision.outcome == "refuse"
    assert not decision.executed


def test_reversible_tool_not_executed_in_shadow(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    fake_actions = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake_actions)
    for spec in default_specs():
        reg.register(spec)
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)

    req = CommandRequest(raw_text="research the market", intent=Intent.UNKNOWN, confidence=0.0)
    raw = json.dumps(
        {"tool_call": {"name": "research.run", "args": {"goal": "market trends"}}}
    )
    decision = route_miss("research the market", rule_request=req, llm_fn=_llm(raw))
    assert decision.outcome == "clarify"
    assert decision.fallback_reason == "safety_class_blocked"
    assert fake_actions.calls == []
    lines = _audit_lines(tmp_path)
    assert lines[-1]["executed"] is False


def test_valid_readonly_tool_call_logged_not_executed(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    fake_actions = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake_actions)
    for spec in default_specs():
        reg.register(spec)
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)

    req = CommandRequest(raw_text="what can you do", intent=Intent.UNKNOWN, confidence=0.0)
    raw = json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})
    decision = route_miss("what can you do", rule_request=req, llm_fn=_llm(raw))
    assert decision.outcome == "tool_call"
    assert decision.mapped_intent == "show_capabilities"
    assert decision.executed is False
    assert fake_actions.calls == []
    lines = _audit_lines(tmp_path)
    assert lines[-1]["selected_tool"] == "assistant.capabilities"
    assert lines[-1]["executed"] is False


def test_production_routing_unchanged_with_shadow(monkeypatch):
    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    monkeypatch.setattr("config.LLM_CLASSIFIER_ENABLED", False, raising=False)
    monkeypatch.setattr("config.SEMANTIC_UNDERSTANDING_ENABLED", False, raising=False)

    from brain.intent_classifier import classify
    from brain.llm_tool_router import get_router_invoke_count, set_llm_fn_for_tests
    from brain.router import CommandRouter

    set_llm_fn_for_tests(_llm('{"no_tool": true}'))
    router = CommandRouter()

    before = get_router_invoke_count()
    result = router.route("show capabilities")
    assert result.intent == Intent.SHOW_CAPABILITIES
    assert get_router_invoke_count() == before

    miss = classify("xyzzy unmapped phrase phase79")
    assert miss.intent in (Intent.UNKNOWN, Intent.CLARIFY)
    router.route("xyzzy unmapped phrase phase79")
    assert get_router_invoke_count() > before


def test_circuit_breaker_on_llm_error(monkeypatch, tmp_path):
    from brain.llm_tool_router import (
        get_router_invoke_count,
        is_circuit_breaker_open,
        route_miss,
    )

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)

    def _boom(_s: str, _u: str) -> str:
        raise RuntimeError("llm down")

    req = CommandRequest(raw_text="a", intent=Intent.UNKNOWN, confidence=0.0)
    for _ in range(3):
        route_miss("a", rule_request=req, llm_fn=_boom)
    assert is_circuit_breaker_open()
    before = get_router_invoke_count()
    route_miss("a", rule_request=req, llm_fn=_llm('{"no_tool": true}'))
    assert get_router_invoke_count() == before + 1
    lines = _audit_lines(tmp_path)
    assert any(line.get("circuit_breaker_open") for line in lines)
