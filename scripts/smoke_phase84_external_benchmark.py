"""Smoke: Phase 84 external holdout benchmark (static analysis only)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from builder_core.external_benchmark import evaluate_holdout, format_holdout_report


def main() -> int:
    report = evaluate_holdout()
    print(format_holdout_report(report))
    if not report.get("available"):
        print("SMOKE SKIP phase84_external_benchmark (holdout missing)")
        return 0
    ok = report["cases_analyzed"] >= 10
    if report["false_positives"] > 0:
        print(f"NOTE: holdout false positives={report['false_positives']} (precision={report['precision']:.4f})")
    print("SMOKE PASS phase84_external_benchmark" if ok else "SMOKE FAIL phase84_external_benchmark")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
