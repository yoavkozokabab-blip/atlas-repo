#!/usr/bin/env python3
"""Phase 78 smoke — Tool Registry catalog integrity.

Builds the default catalog and asserts: 40 tools, 0 FORBIDDEN, 0 denylisted
mappings, all mapped intents implemented. Deterministic; no network/browser.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from actions.registry import ActionRegistry
    from config import IMPLEMENTED_INTENTS
    from tools.registry import ToolRegistry, MOCK_SUCCESS_DENYLIST
    from tools.catalog import default_specs
    from tools.spec import SafetyClass

    reg = ToolRegistry(action_registry=ActionRegistry())
    for spec in default_specs():
        reg.register(spec)

    specs = reg.all()
    counts = reg.by_safety_class()
    print(f"tools registered: {len(specs)}")
    print(f"by safety_class: {counts}")

    problems = []
    if len(specs) != 40:
        problems.append(f"expected 40 tools, got {len(specs)}")
    if counts.get("irreversible_forbidden", 0) != 0:
        problems.append("FORBIDDEN tool present")
    for s in specs:
        if s.maps_to_intent in MOCK_SUCCESS_DENYLIST:
            problems.append(f"{s.name} maps to denylisted handler {s.maps_to_intent}")
        if s.maps_to_intent not in IMPLEMENTED_INTENTS:
            problems.append(f"{s.name} maps to unimplemented intent {s.maps_to_intent}")

    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
        print("SMOKE FAIL phase78_tool_registry")
        return 1
    print("SMOKE PASS phase78_tool_registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
