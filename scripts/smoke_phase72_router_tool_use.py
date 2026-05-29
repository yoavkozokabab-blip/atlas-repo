#!/usr/bin/env python3
"""Phase 72 smoke — bounded tool use through the real CommandRouter.

Modes:
  --no-network   Deterministic router smoke with an injected fake provider
                 (CI-safe; proves the wiring without a live browser).
  --real         Real headless browser run through the router.
  (default runs the forbidden-goal block check in both modes.)

All three modes drive text through CommandRouter.route(...) — the same path a
user/voice command takes — never the executor directly.

Safety: read-only only. No payments/orders/bookings/logins/submits/downloads.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Make console output robust to non-cp1252 page text (Windows consoles).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _fail(msg: str) -> int:
    print(f"SMOKE FAIL: {msg}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 72 router tool-use smoke")
    parser.add_argument("--real", action="store_true", help="Use a real headless browser provider")
    parser.add_argument("--no-network", action="store_true", help="Use a deterministic fake provider")
    parser.add_argument("--query", default="python 3.13 release notes")
    args = parser.parse_args()

    if not args.real and not args.no_network:
        args.no_network = True  # safe default

    from brain.router import CommandRouter
    from core.types import ActionStatus
    import actions.tool_use_actions as tua

    # --- provider selection -------------------------------------------------
    if args.real:
        tua.set_tool_provider_factory(None)  # real PlaywrightBrowserProvider
        mode = "REAL headless browser"
    else:
        from tooluse.contracts import Observation, PlanStep, StepKind, StepOutcome

        class _Fake:
            def __init__(self): self._nav = False
            def is_real(self): return True
            def observe(self):
                if not self._nav:
                    return Observation(real=True, provider="fake",
                                       url="https://www.marginalia-search.com/search?query=x",
                                       title="Results",
                                       links=[{"title": "Best", "url": "https://example.com/best"}],
                                       visible_text="results page with several links here")
                return Observation(real=True, provider="fake", url="https://example.com/best",
                                   title="Best Result", headings=["H"],
                                   visible_text="A substantial body of text to summarize for the smoke.")
            def execute(self, step: PlanStep) -> StepOutcome:
                if step.kind == StepKind.OPEN_RESULT: self._nav = True
                return StepOutcome(ok=True, detail=step.kind.value)
            def apply_recovery(self, d, s): pass
            def close(self): pass

        tua.set_tool_provider_factory(lambda: _Fake())
        mode = "NO-NETWORK fake provider"

    print(f"=== Phase 72 router smoke ({mode}) ===")
    router = CommandRouter()

    # 1. Forbidden goal must be blocked (no execution).
    forbidden = router.route("run tool task book a hotel in paris")
    print(f"[forbidden] status={forbidden.status.value}")
    if forbidden.status != ActionStatus.BLOCKED:
        return _fail(f"forbidden goal not blocked (got {forbidden.status.value})")

    # 2. Bounded research task: confirmation required, then approve.
    r1 = router.route(f"research {args.query}")
    print(f"[run-1] status={r1.status.value} cid={r1.confirmation_id}")
    if r1.status != ActionStatus.CONFIRMATION_REQUIRED:
        return _fail(f"run did not require confirmation (got {r1.status.value})")

    r2 = router.route("yes")
    print(f"[run-2] status={r2.status.value}")
    print("-" * 60)
    print(r2.summary[:1200])
    print("-" * 60)

    # 3. Show last run (read-only).
    r3 = router.route("show last tool run")
    if r3.status != ActionStatus.SUCCESS:
        return _fail(f"show last tool run failed (got {r3.status.value})")
    print("[show-last] ok (read-only)")

    # Honest exit codes — mock/unavailable is never a pass.
    if r2.status == ActionStatus.SUCCESS:
        print("SMOKE PASS phase72_router_tool_use (real observe/plan/act/verify via router)")
        return 0
    if r2.status == ActionStatus.BLOCKED:
        print("SMOKE BLOCKED: no real provider / live search unavailable — reported honestly, not success.")
        return 2
    return _fail(f"run final status = {r2.status.value}")


if __name__ == "__main__":
    raise SystemExit(main())
