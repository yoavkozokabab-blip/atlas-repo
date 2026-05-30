"""Smoke: Phase 79 LLM router safety — forbidden, hallucination, flag-off parity."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    from brain.llm_tool_router import (
        allow_llm_fn_injection_for_tests,
        get_router_invoke_count,
        reset_llm_tool_router_for_tests,
        route_miss,
        set_llm_fn_for_tests,
        set_tool_registry_for_tests,
        shadow_route_miss,
    )
    from core.types import CommandRequest, Intent
    from tests.test_phase78_tool_registry import FakeActionRegistry
    from tools.catalog import default_specs
    from tools.registry import ToolRegistry, reset_for_tests as reset_tool_registry

    reset_llm_tool_router_for_tests()
    reset_tool_registry()
    allow_llm_fn_injection_for_tests()
    ok = True

    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    for spec in default_specs():
        reg.register(spec)

    set_tool_registry_for_tests(reg)

    def _llm(raw: str):
        def _fn(_s: str, _u: str) -> str:
            return raw

        return _fn

    req = CommandRequest(raw_text="x", intent=Intent.UNKNOWN, confidence=0.0)

    os.environ["LLM_TOOL_ROUTER_ENABLED"] = "false"
    os.environ["LLM_TOOL_ROUTER_SHADOW"] = "false"
    set_llm_fn_for_tests(_llm(json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})))
    shadow_route_miss("x", rule_request=req)
    if get_router_invoke_count() != 0:
        print("FAIL router ran with flags off")
        ok = False
    else:
        print("OK flag-off parity")

    os.environ["LLM_TOOL_ROUTER_ENABLED"] = "true"
    os.environ["LLM_TOOL_ROUTER_SHADOW"] = "true"

    buy = route_miss(
        "buy me a laptop today",
        rule_request=req,
        llm_fn=_llm(json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})),
    )
    if buy.outcome != "refuse":
        print(f"FAIL forbidden outcome={buy.outcome}")
        ok = False
    else:
        print("OK forbidden request refused")

    hall = route_miss(
        "odd request",
        rule_request=req,
        llm_fn=_llm(json.dumps({"tool_call": {"name": "not.real", "args": {}}})),
    )
    if hall.outcome != "no_tool":
        print(f"FAIL hallucinated tool outcome={hall.outcome}")
        ok = False
    else:
        print("OK hallucinated tool -> no_tool")

    junk = route_miss("odd", rule_request=req, llm_fn=_llm("<<<not json>>>"))
    if junk.outcome != "no_tool":
        print(f"FAIL malformed outcome={junk.outcome}")
        ok = False
    else:
        print("OK malformed output -> no_tool")

    if fake.calls:
        print("FAIL actions executed during safety smoke")
        ok = False
    else:
        print("OK no tool execution")

    set_tool_registry_for_tests(None)
    set_llm_fn_for_tests(None)
    print("SMOKE PASS phase79_safety" if ok else "SMOKE FAIL phase79_safety")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
