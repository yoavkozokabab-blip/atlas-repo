#!/usr/bin/env python3
"""Phase 78 smoke — safety & no-mock guarantees.

Asserts: FORBIDDEN tools rejected; denylisted (mock-success) handlers rejected;
REVERSIBLE tools blocked without approval; an underlying SUCCESS carrying
mock/unavailable markers is never verified as real. Deterministic; no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from core.types import ActionStatus, CommandResult, Intent
    from tools.registry import ToolRegistry, ToolRegistrationError
    from tools.spec import (
        SafetyClass, SideEffect, ToolSpec, ToolStatus, Verification,
    )

    class FakeReg:
        def has(self, intent): return True
        def execute(self, request):
            return CommandResult(intent=request.intent, status=ActionStatus.SUCCESS,
                                 summary="MOCK MODE | NO REAL EXTERNAL ACCESS",
                                 data={"final_status": "blocked_unavailable"})

    def spec(name, intent, sc=SafetyClass.READ_ONLY, se=SideEffect.NONE,
             verify=(Verification.RESULT_SUCCESS,)):
        return ToolSpec(name=name, version=1, description="t",
                        input_schema={"properties": {}, "required": []}, output_schema={},
                        safety_class=sc, side_effects=se, idempotent=True,
                        verification=tuple(verify), maps_to_intent=intent)

    checks = []

    reg = ToolRegistry(action_registry=FakeReg())

    # 1. FORBIDDEN rejected
    try:
        reg.register(spec("x.forbidden", "show_capabilities", sc=SafetyClass.IRREVERSIBLE_FORBIDDEN))
        checks.append(("forbidden_rejected", False))
    except ToolRegistrationError:
        checks.append(("forbidden_rejected", True))

    # 2. denylisted mock handler rejected
    try:
        reg.register(spec("web.bad", "find_information_about"))
        checks.append(("denylist_rejected", False))
    except ToolRegistrationError:
        checks.append(("denylist_rejected", True))

    # 3. REVERSIBLE blocked without approval
    reg.register(spec("research.run", "run_tool_task", sc=SafetyClass.REVERSIBLE,
                      se=SideEffect.EXTERNAL_REVERSIBLE, verify=(Verification.PROVIDER_REAL,)))
    r = reg.invoke("research.run", {}, allowed_classes=frozenset({SafetyClass.REVERSIBLE}))
    checks.append(("reversible_needs_approval", r.status == ToolStatus.NEEDS_APPROVAL))

    # 4. mock/unavailable never verified as real (even if approved)
    r2 = reg.invoke("research.run", {}, allowed_classes=frozenset({SafetyClass.REVERSIBLE}), approved=True)
    checks.append(("mock_not_verified", r2.verified is False))

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(f"  {name:26s} {'OK' if passed else 'FAIL'}")
    print("SMOKE PASS phase78_tool_safety" if ok else "SMOKE FAIL phase78_tool_safety")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
