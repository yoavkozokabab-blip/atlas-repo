"""Create and manage pilot run records for the Agent/Atlas benchmark.

This script does not automate Codex or Cursor. It emits run records that can be
filled by a real runner, or marks technical failures when a runner is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "tasks"
RUNS_DIR = ROOT / "runs"
REPOSITORIES_PATH = ROOT / "repositories.json"

CONDITIONS = (
    "codex_no_atlas",
    "codex_with_atlas",
    "cursor_no_atlas",
    "cursor_with_atlas",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tasks() -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(TASKS_DIR.glob("task_*.json"))]


def load_repositories() -> dict[str, dict[str, Any]]:
    raw = load_json(REPOSITORIES_PATH)
    return {repo["id"]: repo for repo in raw.get("repositories", [])}


def select_tasks(tasks: Iterable[dict[str, Any]], selected: list[str] | None) -> list[dict[str, Any]]:
    if not selected:
        return list(tasks)
    wanted = set(selected)
    return [task for task in tasks if task["task_id"] in wanted]


def select_conditions(selected: list[str] | None) -> list[str]:
    if not selected:
        return list(CONDITIONS)
    bad = sorted(set(selected) - set(CONDITIONS))
    if bad:
        raise SystemExit(f"Unknown condition(s): {', '.join(bad)}")
    return selected


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def anonymous_id(task_id: str, condition: str, repeat: int, created_at: str) -> str:
    seed = f"{task_id}:{condition}:{repeat}:{created_at}"
    return "run_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def write_run_record(
    *,
    task: dict[str, Any],
    repo: dict[str, Any],
    condition: str,
    repeat: int,
    status: str,
    reason: str,
    force: bool,
) -> Path:
    created_at = now_iso()
    stamp = created_at.replace(":", "").replace("+", "Z")
    run_id = f"{task['task_id']}_{condition}_r{repeat}_{stamp}"
    path = RUNS_DIR / condition / f"{run_id}.json"
    if path.exists() and not force:
        raise SystemExit(f"Run record already exists: {path}")

    record = {
        "schema_version": 1,
        "run_id": run_id,
        "anonymous_id": anonymous_id(task["task_id"], condition, repeat, created_at),
        "created_at": created_at,
        "started_at": None,
        "ended_at": created_at if status == "technical_failure" else None,
        "condition": condition,
        "task_id": task["task_id"],
        "repository_id": task["repository_id"],
        "repository_commit_sha": repo.get("commit_sha"),
        "category": task["category"],
        "difficulty": task["difficulty"],
        "prompt_sha256": prompt_hash(task["prompt"]),
        "prompt": task["prompt"],
        "status": status,
        "response_text": "",
        "runner": {
            "agent": condition.split("_", 1)[0],
            "atlas_required": condition.endswith("with_atlas"),
            "model": None,
            "tool_version": None,
            "system_instructions_fingerprint": None
        },
        "observations": {
            "latency_ms": None,
            "time_to_first_correct_answer_ms": None,
            "token_usage": None,
            "tool_calls": [],
            "atlas_calls": [],
            "files_opened": [],
            "errors": [reason] if reason else [],
            "retries": 0
        },
        "manual_scores": None,
        "notes": reason
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def list_tasks(tasks: list[dict[str, Any]]) -> None:
    for task in tasks:
        order = ", ".join(task.get("condition_order") or CONDITIONS)
        print(f"{task['task_id']} | {task['repository_id']} | {task['category']} | {task['difficulty']}")
        print(f"  {task['title']}")
        print(f"  condition_order: {order}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List pilot tasks.")
    parser.add_argument("--emit-pending", action="store_true", help="Create pending run records.")
    parser.add_argument("--mark-unavailable", action="store_true", help="Create technical-failure run records.")
    parser.add_argument("--reason", default="", help="Reason for --mark-unavailable.")
    parser.add_argument("--task", action="append", help="Limit to a task id. Can be repeated.")
    parser.add_argument("--condition", action="append", help="Limit to a condition. Can be repeated.")
    parser.add_argument("--repeat", type=int, default=1, help="Number of repeats to emit per task/condition.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting an identical path.")
    args = parser.parse_args()

    tasks = select_tasks(load_tasks(), args.task)
    repositories = load_repositories()
    conditions = select_conditions(args.condition)

    if args.list:
        list_tasks(tasks)
        return 0

    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")

    if not args.emit_pending and not args.mark_unavailable:
        parser.print_help()
        return 0

    if args.emit_pending and args.mark_unavailable:
        raise SystemExit("Use either --emit-pending or --mark-unavailable, not both.")

    status = "technical_failure" if args.mark_unavailable else "pending_manual_or_external_run"
    reason = args.reason
    if args.mark_unavailable and not reason:
        reason = "Runner unavailable; no valid benchmark response was produced."

    written: list[Path] = []
    for task in tasks:
        repo = repositories.get(task["repository_id"])
        if not repo:
            raise SystemExit(f"Unknown repository_id for {task['task_id']}: {task['repository_id']}")
        for repeat in range(1, args.repeat + 1):
            ordered = [c for c in task.get("condition_order", CONDITIONS) if c in conditions]
            for condition in ordered:
                written.append(
                    write_run_record(
                        task=task,
                        repo=repo,
                        condition=condition,
                        repeat=repeat,
                        status=status,
                        reason=reason,
                        force=args.force,
                    )
                )

    print(f"Wrote {len(written)} run record(s).")
    for path in written[:12]:
        print(path)
    if len(written) > 12:
        print(f"... {len(written) - 12} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
