"""Smoke: Phase 79 fake-LLM router — deterministic decisions, no execution."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    os.environ["LLM_TOOL_ROUTER_ENABLED"] = "true"
    os.environ["LLM_TOOL_ROUTER_SHADOW"] = "true"

    from brain.llm_tool_router import (
        allow_llm_fn_injection_for_tests,
        reset_llm_tool_router_for_tests,
        route_miss,
        set_llm_fn_for_tests,
        set_tool_registry_for_tests,
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

    cases = {
        "what can you do today": json.dumps(
            {"tool_call": {"name": "assistant.capabilities", "args": {}}}
        ),
        "phase79 nonsense utterance": json.dumps({"clarify": "Which area should I check?"}),
        "totally unknown": json.dumps({"tool_call": {"name": "not.real.tool", "args": {}}}),
        "garbage": "Here you go: {\"no_tool\": true}",
        "buy me stocks now": json.dumps({"refuse": "Cannot purchase"}),
    }

    def _fake_llm(_system: str, user: str) -> str:
        request = user.split("Candidate tools:")[0].strip().lower()
        for key, payload in cases.items():
            if key in request:
                return payload
        return json.dumps({"no_tool": true})

    set_llm_fn_for_tests(_fake_llm)
    req = CommandRequest(raw_text="", intent=Intent.UNKNOWN, confidence=0.0)

    checks = [
        ("what can you do today", "tool_call"),
        ("phase79 nonsense utterance", "clarify"),
        ("totally unknown", "no_tool"),
        ("garbage input please", "no_tool"),
        ("buy me stocks now", "refuse"),
    ]
    for phrase, expected in checks:
        decision = route_miss(
            phrase,
            rule_request=req.model_copy(update={"raw_text": phrase}),
            llm_fn=_fake_llm,
        )
        if decision.outcome != expected:
            print(f"FAIL {phrase!r} expected {expected} got {decision.outcome}")
            ok = False
        else:
            print(f"OK {phrase!r} -> {decision.outcome}")

    if fake.calls:
        print("FAIL tool registry executed during fake smoke")
        ok = False
    else:
        print("OK no tool execution")

    set_tool_registry_for_tests(None)
    set_llm_fn_for_tests(None)
    print("SMOKE PASS phase79_fake" if ok else "SMOKE FAIL phase79_fake")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
