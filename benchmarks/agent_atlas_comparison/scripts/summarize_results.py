"""Summarize completed benchmark run JSON files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark_runner.paths import RUNS_DIR
from benchmark_runner.summary import summarize_to_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR)
    args = parser.parse_args()
    summary = summarize_to_files(args.runs_root)
    print(f"Completed runs: {summary['overall']['completed_runs']}")
    print("Wrote scores/summary.csv and reports/benchmark_report.{json,md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
