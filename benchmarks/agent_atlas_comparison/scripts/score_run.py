"""Score completed benchmark run JSON files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark_runner.paths import RUNS_DIR
from benchmark_runner.scoring import apply_score_to_run, score_file_or_glob


def parse_manual(values: list[str] | None) -> dict[str, int] | None:
    if not values:
        return None
    out: dict[str, int] = {}
    for item in values:
        key, raw_value = item.split("=", 1)
        out[key] = int(raw_value)
    required = {
        "correctness",
        "completeness",
        "citation_accuracy",
        "evidence_quality",
        "hallucination_avoidance",
        "actionability",
    }
    missing = sorted(required - set(out))
    if missing:
        raise SystemExit(f"Missing manual score field(s): {', '.join(missing)}")
    out["strict_success"] = int(sum(out[k] for k in required) >= 24)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", type=Path, help="Score one run JSON.")
    parser.add_argument("--runs-root", type=Path, default=RUNS_DIR, help="Score all runs under this root.")
    parser.add_argument(
        "--manual",
        action="append",
        help="Manual score key=value. Repeat for six fields; otherwise heuristic_v1 is used.",
    )
    args = parser.parse_args()

    targets = [args.run_json] if args.run_json else score_file_or_glob(args.runs_root)
    manual = parse_manual(args.manual)
    scored = 0
    skipped = 0
    for path in targets:
        before = path.read_text(encoding="utf-8")
        record = apply_score_to_run(path, manual_scores=manual)
        after = path.read_text(encoding="utf-8")
        if before != after:
            scored += 1
        else:
            skipped += 1
        if record.get("status") == "completed":
            print(f"Scored: {path}")
    print(f"Updated {scored}; skipped/unchanged {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
