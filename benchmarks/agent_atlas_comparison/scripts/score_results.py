"""Validate run records and export raw scoring tables.

Completed runs must include a `manual_scores` object with six 0-5 fields. The
script does not infer scores from prose.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
SCORES_DIR = ROOT / "scores"

SCORE_FIELDS = (
    "correctness",
    "completeness",
    "citation_accuracy",
    "evidence_quality",
    "hallucination_avoidance",
    "actionability",
)

CONDITIONS = (
    "codex_no_atlas",
    "codex_with_atlas",
    "cursor_no_atlas",
    "cursor_with_atlas",
)


def iter_run_paths() -> list[Path]:
    paths: list[Path] = []
    for condition in CONDITIONS:
        paths.extend(sorted((RUNS_DIR / condition).glob("*.json")))
    return paths


def load_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_score(value: Any, field: str, run_id: str) -> int:
    if not isinstance(value, int) or value < 0 or value > 5:
        raise SystemExit(f"{run_id}: manual_scores.{field} must be an integer 0..5")
    return value


def score_record(record: dict[str, Any]) -> dict[str, Any]:
    scores = record.get("manual_scores")
    status = record.get("status", "")
    technical_failure = status == "technical_failure"
    row: dict[str, Any] = {
        "anonymous_id": record.get("anonymous_id", ""),
        "run_id": record.get("run_id", ""),
        "task_id": record.get("task_id", ""),
        "condition": record.get("condition", ""),
        "repository_id": record.get("repository_id", ""),
        "repository_commit_sha": record.get("repository_commit_sha", ""),
        "category": record.get("category", ""),
        "difficulty": record.get("difficulty", ""),
        "status": status,
        "scored": "false",
        "technical_failure": "true" if technical_failure else "false",
        "latency_ms": (record.get("observations") or {}).get("latency_ms"),
        "tool_call_count": len((record.get("observations") or {}).get("tool_calls") or []),
        "atlas_call_count": len((record.get("observations") or {}).get("atlas_calls") or []),
        "files_opened_count": len((record.get("observations") or {}).get("files_opened") or []),
        "error": "; ".join((record.get("observations") or {}).get("errors") or []),
    }

    for field in SCORE_FIELDS:
        row[field] = ""
    row["total_score"] = ""

    if scores is not None:
        total = 0
        for field in SCORE_FIELDS:
            value = normalize_score(scores.get(field), field, record.get("run_id", "unknown"))
            row[field] = value
            total += value
        row["total_score"] = total
        row["scored"] = "true"

    return row


def write_blinded_packet(records: list[dict[str, Any]]) -> None:
    path = SCORES_DIR / "blinded_runs.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            packet = {
                "anonymous_id": record.get("anonymous_id"),
                "task_id": record.get("task_id"),
                "repository_id": record.get("repository_id"),
                "category": record.get("category"),
                "difficulty": record.get("difficulty"),
                "prompt": record.get("prompt"),
                "status": record.get("status"),
                "response_text": record.get("response_text"),
                "errors": (record.get("observations") or {}).get("errors") or [],
            }
            handle.write(json.dumps(packet, ensure_ascii=False) + "\n")


def main() -> int:
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    records = [load_record(path) for path in iter_run_paths()]
    rows = [score_record(record) for record in records]

    fieldnames = [
        "anonymous_id",
        "run_id",
        "task_id",
        "condition",
        "repository_id",
        "repository_commit_sha",
        "category",
        "difficulty",
        "status",
        "scored",
        "technical_failure",
        "latency_ms",
        "tool_call_count",
        "atlas_call_count",
        "files_opened_count",
        *SCORE_FIELDS,
        "total_score",
        "error",
    ]

    raw_path = SCORES_DIR / "raw_scores.csv"
    with raw_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    write_blinded_packet(records)

    scored_totals = [int(row["total_score"]) for row in rows if row["scored"] == "true"]
    if scored_totals:
        print(
            f"Wrote {raw_path} with {len(scored_totals)} scored run(s); "
            f"median score {median(scored_totals):.1f}."
        )
    else:
        print(f"Wrote {raw_path}; no scored completed runs found.")
    print(f"Wrote {SCORES_DIR / 'blinded_runs.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
