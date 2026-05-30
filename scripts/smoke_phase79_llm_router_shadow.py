"""Smoke: Phase 79 router shadow mode — logs only, classifier result unchanged."""

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
    os.environ["SEMANTIC_UNDERSTANDING_ENABLED"] = "false"

    import config as cfg

    cfg.SEMANTIC_UNDERSTANDING_ENABLED = False
    cfg.LLM_CLASSIFIER_ENABLED = False

    from brain.llm_tool_router import (
        allow_llm_fn_injection_for_tests,
        reset_llm_tool_router_for_tests,
        set_llm_fn_for_tests,
        set_tool_registry_for_tests,
    )
    from brain.router import CommandRouter
    from core.types import Intent
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

    def _fake_llm(_system: str, user: str) -> str:
        request_part = user.split("Candidate tools:")[0].lower()
        if "show capabilities" in request_part:
            return json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})
        return json.dumps({"clarify": "Which topic should I focus on?"})

    set_llm_fn_for_tests(_fake_llm)

    from brain import llm_tool_router

    router = CommandRouter()
    before = llm_tool_router.get_router_invoke_count()
    hit = router.route("show capabilities")
    if hit.intent != Intent.SHOW_CAPABILITIES:
        print(f"FAIL confident route intent={hit.intent}")
        ok = False
    elif llm_tool_router.get_router_invoke_count() != before:
        print("FAIL shadow router invoked on confident hit")
        ok = False
    else:
        print("OK confident hit skips shadow router")

    miss = router.route("phase79 router shadow unmapped phrase")
    if miss.intent not in (Intent.UNKNOWN, Intent.CLARIFY):
        print(f"FAIL classifier result changed to {miss.intent}")
        ok = False
    elif llm_tool_router.get_router_invoke_count() <= before:
        print("FAIL shadow router not invoked on miss")
        ok = False
    elif fake.calls:
        print("FAIL tool executed during shadow")
        ok = False
    else:
        print(f"OK classifier unchanged on miss ({miss.intent.value})")

    from config import DATA_DIR

    audit_path = Path(DATA_DIR) / "llm_router_audit.jsonl"
    if not audit_path.is_file():
        print("FAIL audit missing")
        ok = False
    else:
        last = json.loads(audit_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        blob = json.dumps(last)
        if last.get("executed") is not False:
            print("FAIL audit executed flag")
            ok = False
        elif "user_text" in last or "llm_raw" in blob.lower():
            print("FAIL audit leaked raw user/llm payload")
            ok = False
        else:
            print(f"OK audit outcome={last.get('outcome')!r} fingerprint={last.get('user_fingerprint')!r}")

    set_tool_registry_for_tests(None)
    set_llm_fn_for_tests(None)

    print("SMOKE PASS phase79_llm_router_shadow" if ok else "SMOKE FAIL phase79_llm_router_shadow")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
