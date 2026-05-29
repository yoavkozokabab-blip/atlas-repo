#!/usr/bin/env python3
"""Phase 78 smoke — adapter parity.

Invokes several READ_ONLY tools through the Tool Registry and confirms the
resulting status matches the direct ActionRegistry path (proves the registry is
additive and non-breaking). Deterministic; no network/browser.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Tools known to take no required args and to be safe READ_ONLY.
_PARITY = [
    ("assistant.capabilities", "show_capabilities"),
    ("assistant.list_skills", "list_skills"),
    ("system.health", "show_system_health"),
    ("system.status", "show_system_status"),
    ("system.runtime_status", "show_runtime_status"),
]


def main() -> int:
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent
    from tools.registry import ToolRegistry
    from tools.catalog import default_specs

    action_reg = ActionRegistry()
    treg = ToolRegistry(action_registry=action_reg)
    for spec in default_specs():
        treg.register(spec)

    mismatches = []
    for tool_name, intent in _PARITY:
        tool_res = treg.invoke(tool_name, {})
        direct = action_reg.execute(CommandRequest(raw_text=intent, intent=Intent(intent)))
        # tool ToolStatus.value vs ActionStatus.value should agree on success/non-success
        same = (tool_res.status.value == "success") == (direct.status.value == "success")
        print(f"  {tool_name:28s} tool={tool_res.status.value:14s} direct={direct.status.value:14s} "
              f"{'OK' if same else 'MISMATCH'}")
        if not same:
            mismatches.append(tool_name)

    if mismatches:
        print(f"SMOKE FAIL phase78_tool_parity ({len(mismatches)} mismatch)")
        return 1
    print("SMOKE PASS phase78_tool_parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
