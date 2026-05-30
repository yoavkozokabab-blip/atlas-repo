"""Run the external holdout benchmark through the UNIFIED ENGINE (Phase 92A).

Primary output (pass/fail) comes from the unified engine for both the QuixBugs
in-domain baseline and the out-of-domain holdout. The legacy semantic-path
numbers are printed only as a clearly labeled comparison and never drive
pass/fail. Read-only static analysis; no target code is executed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from builder_core.bug_intelligence import engine_benchmark

QUIXBUGS = r"C:\Repos\QuixBugs"


def main() -> int:
    print("=== QuixBugs baseline (in-domain) — unified engine ===")
    quix = engine_benchmark.evaluate_quixbugs_engine(QUIXBUGS)
    print(engine_benchmark.format_report(quix))
    print()

    print("=== External holdout (out-of-domain / transfer) — unified engine ===")
    holdout = engine_benchmark.evaluate_holdout_engine()
    print(engine_benchmark.format_holdout_report(holdout))

    # --- legacy comparison only (does NOT drive pass/fail) ---------------
    try:
        from builder_core import external_benchmark as legacy_holdout
        legacy = legacy_holdout.evaluate_holdout()
        if legacy.get("available"):
            print()
            print("=== [comparison only] legacy semantic-path holdout ===")
            print(f"cases analyzed: {legacy['cases_analyzed']}")
            print(f"true positives: {legacy['true_positives']}")
            print(f"false positives: {legacy['false_positives']}")
            print(f"precision: {legacy['precision']:.4f}")
            print(f"recall: {legacy['recall']:.4f}")
    except Exception:
        pass  # comparison is optional and must never affect the result

    # pass/fail is driven solely by the unified-engine holdout.
    return 0 if holdout.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
