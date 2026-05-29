#!/usr/bin/env python3
"""Phase 70 smoke: agent facades + no command regression."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _fail(msg: str) -> None:
    print(f"SMOKE FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    from agents import (
        AgentId,
        agent_for_intent,
        get_executive_agent,
        get_memory_agent,
        get_operator_agent,
        get_conversation_agent,
    )
    from core.types import CommandRequest, Intent
    from brain.router import CommandRouter

    exec_agent = get_executive_agent()
    catalog = exec_agent.capability_catalog()
    if len(catalog) != 7:
        _fail(f"expected 7 agent capabilities, got {len(catalog)}")

    assert agent_for_intent(Intent.REMEMBER_FACT) == AgentId.MEMORY
    assert agent_for_intent(Intent.OPEN_BROWSER) == AgentId.BROWSER
    assert agent_for_intent(Intent.SHOW_VOICE_HEALTH) == AgentId.CONVERSATION
    assert agent_for_intent(Intent.START_TASK) == AgentId.PLANNING

    mem = get_memory_agent()
    eid = mem.remember("phase70 agent test", tags=["phase70"])
    if not eid:
        _fail("memory agent remember failed")
    hits = mem.search("phase70")
    if not hits:
        _fail("memory agent search failed")

    op = get_operator_agent()
    st = op.browser_state()
    if st is None:
        _fail("operator browser state missing")

    conv = get_conversation_agent()
    ctx = conv.classify_context()
    if ctx is None:
        _fail("conversation context missing")

    req = CommandRequest(raw_text="show capabilities", intent=Intent.SHOW_CAPABILITIES)
    delegation = exec_agent.delegate(req)
    if delegation.agent_id != AgentId.EXECUTIVE:
        _fail(f"unexpected agent {delegation.agent_id}")
    if not delegation.result.summary:
        _fail("delegation empty summary")

    router = CommandRouter()
    r1 = router.route("show capabilities")
    r2 = exec_agent.route_text("show capabilities")
    if r1.status != r2.status:
        _fail("router vs executive route_text status mismatch")

    report = ROOT / "reports" / "agent_architecture_report.md"
    if not report.is_file():
        _fail("agent_architecture_report.md missing")

    for name in (
        "executive_agent.py",
        "conversation_agent.py",
        "memory_agent.py",
        "operator_agent.py",
        "research_agent.py",
        "coding_agent.py",
        "planning_agent.py",
    ):
        if not (ROOT / "agents" / name).is_file():
            _fail(f"missing agents/{name}")

    print("SMOKE PASS phase70_agent_architecture")


if __name__ == "__main__":
    main()
