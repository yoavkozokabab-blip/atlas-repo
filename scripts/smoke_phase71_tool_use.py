#!/usr/bin/env python3
"""Phase 71 smoke — real observe/plan/act/verify on a bounded browser task.

Demonstrates: "Search for X, open the most relevant result, summarize what you see."

Safety:
- Read-only task only (no payments/orders/bookings/submits/logins/downloads).
- Every external step is approval-gated. WITHOUT --approve the smoke shows the
  dry-run plan and proves the approval gate blocks execution (APPROVAL_DENIED).
- WITH --approve the operator authorizes execution; a REAL browser is required.
  If Playwright/Chromium is unavailable the run reports BLOCKED_UNAVAILABLE —
  never a fake success.

Usage:
    py scripts/smoke_phase71_tool_use.py                 # dry-run + gate demo
    py scripts/smoke_phase71_tool_use.py --approve        # real headless run
    py scripts/smoke_phase71_tool_use.py --approve --headed --query "mars facts"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 71 real tool-use smoke")
    parser.add_argument("--query", default="python 3.13 release notes",
                        help="Search query / goal for the bounded task")
    parser.add_argument("--approve", action="store_true",
                        help="Operator approves every external step (required for real execution)")
    parser.add_argument("--headed", action="store_true",
                        help="Run a visible browser window (default: headless)")
    args = parser.parse_args()

    from tooluse import (
        ForbiddenGoalError,
        PlaywrightBrowserProvider,
        RunStatus,
        ToolUseExecutor,
        approve_all,
        build_search_open_summarize_plan,
    )
    from tooluse.executor import deny_all

    # 1. PLAN (dry run — nothing executed).
    try:
        plan = build_search_open_summarize_plan(args.query)
    except ForbiddenGoalError as exc:
        print(f"SMOKE: goal correctly rejected as forbidden: {exc}")
        return 0

    print("=" * 70)
    print(plan.format())
    print("=" * 70)

    # 2. APPROVAL gate.
    if args.approve:
        def approver(step):
            print(f"[APPROVAL GRANTED via --approve] step {step.index}: {step.kind.value}")
            return True
    else:
        print("\nNo --approve flag: demonstrating the approval gate (will deny).")
        approver = deny_all

    # 3. EXECUTE with a real provider (no mock branch exists).
    provider = PlaywrightBrowserProvider(headless=not args.headed)
    run = ToolUseExecutor(provider, approver=approver).run(plan)

    print("\n" + "=" * 70)
    print(run.format())
    print("=" * 70)

    # 4. Honest exit codes — mock/unavailable is never "pass".
    if not args.approve:
        if run.status == RunStatus.APPROVAL_DENIED:
            print("SMOKE PASS phase71_tool_use (approval gate enforced; no execution)")
            return 0
        print(f"SMOKE FAIL: expected APPROVAL_DENIED, got {run.status.value}")
        return 1

    if run.status == RunStatus.SUCCESS:
        print("SMOKE PASS phase71_tool_use (real observe/plan/act/verify succeeded)")
        return 0
    if run.status == RunStatus.BLOCKED_UNAVAILABLE:
        print("SMOKE BLOCKED: no real browser provider available — reported honestly, "
              "not counted as success.")
        return 2
    print(f"SMOKE FAIL: run status = {run.status.value}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
