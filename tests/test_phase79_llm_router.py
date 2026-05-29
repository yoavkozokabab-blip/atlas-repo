"""Phase 79 Stage 1 — Shadow LLM tool router (deterministic; fake llm_fn)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.tool_router_prompt import parse_router_output
from core.types import CommandRequest, Intent
from tests.test_phase78_tool_registry import FakeActionRegistry
from tools.catalog import default_specs
from tools.registry import ToolRegistry, reset_for_tests as reset_tool_registry


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    from brain import tool_router_audit
    from brain.llm_tool_router import reset_llm_tool_router_for_tests

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
    maybe_shadow_route_on_miss("show capabilities", hit, llm_fn=_llm('{"no_tool": true}'))
    assert get_router_invoke_count() == 0

    miss = CommandRequest(raw_text="xyzzy", intent=Intent.UNKNOWN, confidence=0.0)
    maybe_shadow_route_on_miss("xyzzy", miss, llm_fn=_llm('{"no_tool": true}'))
    assert get_router_invoke_count() == 1


def test_strict_parse_rejects_prose_wrapped_json():
    kind, _ = parse_router_output('Here is the answer: {"no_tool": true}')
    assert kind == "malformed"


def test_strict_parse_rejects_embedded_json_in_prose():
    kind, _ = parse_router_output(
        'Sure! {"tool_call": {"name": "assistant.capabilities", "args": {}}} thanks'
    )
    assert kind == "malformed"


def test_strict_parse_rejects_extra_top_level_keys():
    kind, _ = parse_router_output('{"no_tool": true, "confidence": 0.9}')
    assert kind == "malformed"


def test_strict_parse_rejects_invalid_no_tool_value():
    kind, _ = parse_router_output('{"no_tool": false}')
    assert kind == "malformed"


def test_malformed_llm_output_no_tool(monkeypatch, tmp_path):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="mystery task", intent=Intent.UNKNOWN, confidence=0.0)
    decision = route_miss("mystery task", rule_request=req, llm_fn=_llm("not json at all"))
    assert decision.outcome == "no_tool"
    lines = _audit_lines(tmp_path)
    assert lines[-1]["outcome"] == "no_tool"
    assert "llm_raw" not in json.dumps(lines[-1]).lower()


def test_hallucinated_tool_rejected(monkeypatch):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="do something odd", intent=Intent.UNKNOWN, confidence=0.0)
    raw = json.dumps({"tool_call": {"name": "fake.tool", "args": {}}})
    decision = route_miss("do something odd", rule_request=req, llm_fn=_llm(raw))
    assert decision.outcome == "no_tool"
    assert decision.fallback_reason in {"not_in_candidates", "hallucinated_tool"}


def test_tool_not_in_supplied_candidates_rejected(monkeypatch):
    from brain.llm_tool_router import route_miss

    _enable_shadow(monkeypatch)
    reg = _build_registry()
    monkeypatch.setattr("tools.catalog.build_default_tool_registry", lambda **_: reg)
    req = CommandRequest(raw_text="xyzzy", intent=Intent.UNKNOWN, confidence=0.0)
    raw = json.dumps({"tool_call": {"name": "research.run", "args": {"goal": "x"}}})
    decision = route_miss("xyzzy", rule_request=req, llm_fn=_llm(raw))
    assert decision.outcome == "no_tool"
    assert decision.fallback_reason == "not_in_candidates"


def test_forbidden_request_refuse(monkeypatch):
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
    assert decision.outcome in {"no_tool", "clarify"}
    assert decision.executed is False
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
    assert decision.tool_name in decision.candidate_tools
    assert decision.mapped_intent == "show_capabilities"
    assert decision.executed is False
    assert fake_actions.calls == []
    lines = _audit_lines(tmp_path)
    assert lines[-1]["selected_tool"] == "assistant.capabilities"
    assert "user_text" not in lines[-1]
    assert "user_fingerprint" in lines[-1]


def test_audit_redacts_secret_like_arg_keys(monkeypatch, tmp_path):
    from brain import tool_router_audit

    tool_router_audit.record_shadow_decision(
        user_text="remember api_key=supersecret",
        classifier_intent="unknown",
        classifier_confidence=0.0,
        classifier_source="rules",
        outcome="tool_call",
        candidate_tools=["memory.remember"],
        selected_tool="memory.remember",
        selected_args={"api_key": "supersecret", "refresh_token": "rt-abc"},
        mapped_intent="remember_fact",
    )
    line = _audit_lines(tmp_path)[-1]
    assert line["selected_args"]["api_key"] == "[REDACTED]"
    assert line["selected_args"]["refresh_token"] == "[REDACTED]"
    assert "supersecret" not in json.dumps(line)
    assert "rt-abc" not in json.dumps(line)


def test_audit_string_values_are_fingerprinted_not_raw(monkeypatch, tmp_path):
    from brain import tool_router_audit

    secret_payload = "my password is hunter2 and token=abc123"
    tool_router_audit.record_shadow_decision(
        user_text=secret_payload,
        classifier_intent="unknown",
        classifier_confidence=0.0,
        classifier_source="rules",
        outcome="tool_call",
        candidate_tools=["memory.recall"],
        selected_tool="memory.recall",
        selected_args={
            "query": "find my api_key=embedded-secret",
            "text": secret_payload,
            "goal": "research nvidia earnings",
        },
        mapped_intent="search_memory",
    )
    line = _audit_lines(tmp_path)[-1]
    blob = json.dumps(line)
    assert "hunter2" not in blob
    assert "embedded-secret" not in blob
    assert "abc123" not in blob
    assert "nvidia earnings" not in blob
    for field in ("query", "text", "goal"):
        meta = line["selected_args"][field]
        assert meta["type"] == "str"
        assert isinstance(meta["length"], int)
        assert meta["length"] > 0
        assert len(meta["sha256"]) == 12
    assert "user_text" not in line
    assert line["user_fingerprint"].startswith("len=")


def test_audit_nested_args_redacted_recursively(monkeypatch, tmp_path):
    from brain import tool_router_audit

    tool_router_audit.record_shadow_decision(
        user_text="nested",
        classifier_intent="unknown",
        classifier_confidence=0.0,
        classifier_source="rules",
        outcome="tool_call",
        candidate_tools=[],
        selected_args={
            "payload": {
                "session": "sess-live",
                "note": "plain note",
                "count": 2,
                "ok": True,
                "tags": ["alpha", "beta"],
            },
        },
    )
    line = _audit_lines(tmp_path)[-1]
    nested = line["selected_args"]["payload"]
    assert nested["session"] == "[REDACTED]"
    assert nested["note"]["type"] == "str"
    assert nested["count"] == 2
    assert nested["ok"] is True
    assert nested["tags"][0]["type"] == "str"
    assert "plain note" not in json.dumps(line)
    assert "sess-live" not in json.dumps(line)


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
    routed = router.route("xyzzy unmapped phrase phase79")
    assert routed.intent in (Intent.UNKNOWN, Intent.CLARIFY)
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
