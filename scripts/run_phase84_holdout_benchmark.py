"""Run Phase 84 external holdout benchmark (read-only static analysis)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from builder_core import benchmark as quixbugs_benchmark
from builder_core.external_benchmark import evaluate_holdout, format_holdout_report


def main() -> int:
    print("=== QuixBugs baseline (in-domain) ===")
    quix = quixbugs_benchmark.evaluate_quixbugs(r"C:\Repos\QuixBugs")
    print(quixbugs_benchmark.format_report(quix))
    print()

    print("=== External holdout (out-of-domain / transfer) ===")
    holdout = evaluate_holdout()
    print(format_holdout_report(holdout))
    return 0 if holdout.get("available") else 1


if __name__ == "__main__":
    raise SystemExit(main())
