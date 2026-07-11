"""Score benchmark runs against gold standards (blinded first)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.gold_scorer import score_run  # noqa: E402
from lib.schema import (  # noqa: E402
    BENCHMARK_ROOT,
    RunArtifact,
    TaskScore,
    dump_json,
    load_json,
    load_tasks,
    parse_gold,
)


def _load_artifacts() -> list[RunArtifact]:
    artifacts: list[RunArtifact] = []
    fields = set(RunArtifact.__dataclass_fields__)
    for condition_dir in (BENCHMARK_ROOT / "runs").iterdir():
        if not condition_dir.is_dir():
            continue
        for path in sorted(condition_dir.glob("pilot_*.json")):
            raw = load_json(path)
            payload = {k: v for k, v in raw.items() if k in fields}
            artifacts.append(RunArtifact(**payload))
    return artifacts


def cmd_score(pilot: bool) -> int:
    tasks = {t.task_id: t for t in load_tasks()}
    artifacts = _load_artifacts()
    if not artifacts:
        print("FAIL no run artifacts found")
        return 1

    scores: list[TaskScore] = []
    for art in artifacts:
        if pilot and not art.task_id.startswith("pilot_"):
            continue
        task = tasks[art.task_id]
        gold = parse_gold(task.gold_path())
        scores.append(score_run(task, gold, art))

    # Blinded scores (no condition column)
    blind_rows = []
    for sc in scores:
        blind_rows.append(
            {
                "blind_id": sc.blind_id,
                "task_id": sc.task_id,
                "correctness": sc.correctness,
                "completeness": sc.completeness,
                "citation_accuracy": sc.citation_accuracy,
                "evidence_quality": sc.evidence_quality,
                "hallucination_avoidance": sc.hallucination_avoidance,
                "actionability": sc.actionability,
                "total_score": sc.total_score,
                "task_success": sc.task_success,
            }
        )
    dump_json(BENCHMARK_ROOT / "scores" / "blinded_scores.json", blind_rows)

    # Revealed scores
    revealed = [sc.to_dict() for sc in scores]
    dump_json(BENCHMARK_ROOT / "scores" / "revealed_scores.json", revealed)

    raw_csv = BENCHMARK_ROOT / "scores" / "raw_scores.csv"
    with raw_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "blind_id",
                "task_id",
                "condition",
                "correctness",
                "completeness",
                "citation_accuracy",
                "evidence_quality",
                "hallucination_avoidance",
                "actionability",
                "total_score",
                "task_success",
                "required_files_miss",
                "hallucinations_found",
            ],
        )
        writer.writeheader()
        for sc in scores:
            writer.writerow(
                {
                    "run_id": sc.run_id,
                    "blind_id": sc.blind_id,
                    "task_id": sc.task_id,
                    "condition": sc.condition,
                    "correctness": sc.correctness,
                    "completeness": sc.completeness,
                    "citation_accuracy": sc.citation_accuracy,
                    "evidence_quality": sc.evidence_quality,
                    "hallucination_avoidance": sc.hallucination_avoidance,
                    "actionability": sc.actionability,
                    "total_score": sc.total_score,
                    "task_success": sc.task_success,
                    "required_files_miss": ";".join(sc.required_files_miss),
                    "hallucinations_found": ";".join(sc.hallucinations_found),
                }
            )

    print(f"Scored {len(scores)} runs -> {raw_csv}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    return cmd_score(args.pilot)


if __name__ == "__main__":
    raise SystemExit(main())
