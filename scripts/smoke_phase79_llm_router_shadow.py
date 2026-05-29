"""Smoke: Phase 79 shadow LLM tool router — logs only, classifier stays authoritative."""

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

    from brain.llm_tool_router import reset_llm_tool_router_for_tests, set_llm_fn_for_tests
    from brain.router import CommandRouter
    from core.types import Intent
    from tests.test_phase78_tool_registry import FakeActionRegistry
    from tools.catalog import default_specs
    from tools.registry import ToolRegistry, reset_for_tests as reset_tool_registry

    reset_llm_tool_router_for_tests()
    reset_tool_registry()
    ok = True

    fake = FakeActionRegistry()
    reg = ToolRegistry(action_registry=fake)
    for spec in default_specs():
        reg.register(spec)

    import tools.catalog as cat

    original_build = cat.build_default_tool_registry

    def _build(**kwargs):
        return reg

    cat.build_default_tool_registry = _build  # type: ignore[assignment]

    def _fake_llm(_system: str, user: str) -> str:
        request_part = user.split("Candidate tools:")[0].lower()
        if "show capabilities" in request_part:
            return json.dumps({"tool_call": {"name": "assistant.capabilities", "args": {}}})
        return json.dumps({"clarify": "Which topic should I focus on?"})

    set_llm_fn_for_tests(_fake_llm)

    from brain import llm_tool_router

    jarvis_router = CommandRouter()
    before = llm_tool_router.get_router_invoke_count()
    hit = jarvis_router.route("show capabilities")
    if hit.intent != Intent.SHOW_CAPABILITIES:
        print(f"FAIL confident route intent={hit.intent}")
        ok = False
    elif llm_tool_router.get_router_invoke_count() != before:
        print("FAIL shadow LLM router invoked on confident hit")
        ok = False
    else:
        print("OK confident hit skips shadow router")

    miss = jarvis_router.route("phase79 shadow smoke unmapped phrase")
    if miss.intent not in (Intent.UNKNOWN, Intent.CLARIFY):
        print(f"FAIL miss route changed to {miss.intent}")
        ok = False
    elif llm_tool_router.get_router_invoke_count() <= before:
        print("FAIL shadow LLM router not invoked on miss")
        ok = False
    elif fake.calls:
        print("FAIL tool registry invoked during shadow")
        ok = False
    else:
        print(f"OK miss shadow logged (route intent={miss.intent.value})")

    from config import DATA_DIR

    audit = Path(DATA_DIR) / "llm_router_audit.jsonl"
    if not audit.is_file():
        print("FAIL audit file missing")
        ok = False
    else:
        last = json.loads(audit.read_text(encoding="utf-8").strip().splitlines()[-1])
        if last.get("executed") is not False:
            print("FAIL audit executed flag")
            ok = False
        else:
            print(f"OK audit outcome={last.get('outcome')!r}")

    cat.build_default_tool_registry = original_build  # type: ignore[assignment]
    set_llm_fn_for_tests(None)

    print("SMOKE PASS phase79_shadow" if ok else "SMOKE FAIL phase79_shadow")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
