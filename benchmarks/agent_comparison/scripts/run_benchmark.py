"""Run agent comparison benchmark (pilot phase)."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import random
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lib.atlas_runner import run_atlas_mcp  # noqa: E402
from lib.baseline_runner import run_baseline  # noqa: E402
from lib.schema import (  # noqa: E402
    BENCHMARK_ROOT,
    CONDITIONS,
    ROOT,
    WITH_ATLAS,
    RunArtifact,
    agent_from_condition,
    dump_json,
    load_repositories,
    load_tasks,
)

PILOT_TASKS = tuple(f"pilot_{i:03d}" for i in range(1, 7))
MODEL_TOOL_VERSION = "pilot_automated_stand_in_v1; codex_cli=unavailable; cursor_cli=present_not_automated"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _repo_commit(repo_meta: Dict[str, Any], repo_path: Path) -> str | None:
    if repo_meta.get("commit_sha"):
        return str(repo_meta["commit_sha"])
    if repo_meta.get("type") == "controlled_fixture":
        files = sorted(repo_path.rglob("*.py"))
        h = hashlib.sha256()
        for f in files:
            h.update(f.read_bytes())
        return f"fixture:{h.hexdigest()[:16]}"
    return None


def cmd_prepare() -> int:
    repos = load_repositories()
    for repo_id, meta in repos.items():
        path = (ROOT / meta["path"]).resolve()
        if not path.exists():
            print(f"FAIL missing repo path: {repo_id} -> {path}")
            return 1
        if meta.get("type") == "git" and (path / ".git").is_dir():
            sha = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True)
                .strip()
            )
            expected = meta.get("commit_sha")
            if expected and sha != expected:
                print(f"WARN {repo_id}: HEAD {sha} != pinned {expected}")
            else:
                print(f"OK {repo_id}: {sha}")
        else:
            print(f"OK {repo_id}: fixture at {path}")
    return 0


def cmd_validate() -> int:
    tasks = load_tasks()
    if len(tasks) != 6:
        print(f"FAIL expected 6 pilot tasks, found {len(tasks)}")
        return 1
    repos = load_repositories()
    for task in tasks:
        if task.repo_id not in repos:
            print(f"FAIL {task.task_id}: unknown repo {task.repo_id}")
            return 1
        if not task.gold_path().is_file():
            print(f"FAIL {task.task_id}: missing gold {task.gold_path()}")
            return 1
        print(f"OK {task.task_id} [{task.category}] -> {task.repo_id}")
    return 0


def _condition_order(seed: int, task_id: str) -> List[str]:
    rng = random.Random(f"{seed}:{task_id}")
    order = list(CONDITIONS)
    rng.shuffle(order)
    return order


def _execute_condition(task, repo_path: Path, condition: str) -> Dict[str, Any]:
    if condition in WITH_ATLAS:
        return run_atlas_mcp(task, repo_path)
    return run_baseline(task, repo_path)


def cmd_pilot(repeats: int, seed: int) -> int:
    tasks = [t for t in load_tasks() if t.task_id in PILOT_TASKS]
    repos = load_repositories()
    manifest: Dict[str, Any] = {
        "phase": "pilot_v1",
        "started_at": _utc_now(),
        "execution_backend": "automated_stand_in",
        "model_tool_version": MODEL_TOOL_VERSION,
        "repeats": repeats,
        "seed": seed,
        "conditions": list(CONDITIONS),
        "runs": [],
        "failures": [],
    }

    run_idx = 0
    blind_map: List[Dict[str, str]] = []

    for task in tasks:
        repo_meta = repos[task.repo_id]
        repo_path = task.repo_path(repos)
        commit = _repo_commit(repo_meta, repo_path)
        order = _condition_order(seed, task.task_id)

        for repeat in range(1, repeats + 1):
            for condition in order:
                run_idx += 1
                blind_id = f"run_{chr(64 + ((run_idx - 1) % 26) + 1)}_{run_idx:03d}"
                run_id = f"{task.task_id}_{condition}_r{repeat}"
                started = _utc_now()
                t0 = dt.datetime.now(dt.timezone.utc)

                result = _execute_condition(task, repo_path, condition)
                ended = _utc_now()
                latency = float(result.get("latency_seconds") or 0)

                artifact = RunArtifact(
                    run_id=run_id,
                    blind_id=blind_id,
                    task_id=task.task_id,
                    condition=condition,
                    agent=agent_from_condition(condition),
                    atlas_enabled=condition in WITH_ATLAS,
                    repeat=repeat,
                    prompt=task.prompt,
                    repo_id=task.repo_id,
                    repo_path=str(repo_path),
                    repo_commit_sha=commit,
                    execution_backend="automated_stand_in",
                    model_tool_version=MODEL_TOOL_VERSION,
                    started_at=started,
                    ended_at=ended,
                    latency_seconds=latency,
                    ok=bool(result.get("ok")),
                    error=str(result.get("error") or ""),
                    response_text=str(result.get("response_text") or ""),
                    tool_calls=list(result.get("tool_calls") or []),
                    atlas_tool_calls=list(result.get("atlas_tool_calls") or []),
                    files_inspected=list(result.get("files_inspected") or []),
                )

                out_dir = BENCHMARK_ROOT / "runs" / condition
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{run_id}.json"
                dump_json(out_path, artifact.to_dict())

                blind_map.append(
                    {
                        "blind_id": blind_id,
                        "run_id": run_id,
                        "condition": condition,
                        "task_id": task.task_id,
                    }
                )
                manifest["runs"].append(
                    {
                        "run_id": run_id,
                        "blind_id": blind_id,
                        "condition": condition,
                        "task_id": task.task_id,
                        "ok": artifact.ok,
                        "latency_seconds": artifact.latency_seconds,
                        "path": str(out_path.relative_to(BENCHMARK_ROOT)),
                    }
                )
                if not artifact.ok:
                    manifest["failures"].append(
                        {"run_id": run_id, "error": artifact.error or "unknown"}
                    )
                print(
                    f"{'OK' if artifact.ok else 'FAIL'} {run_id} "
                    f"latency={artifact.latency_seconds:.2f}s"
                )

    manifest["ended_at"] = _utc_now()
    manifest["run_count"] = len(manifest["runs"])
    dump_json(BENCHMARK_ROOT / "runs" / "pilot_manifest.json", manifest)
    dump_json(BENCHMARK_ROOT / "scores" / "blind_map.json", {"mapping": blind_map})
    print(f"Pilot complete: {manifest['run_count']} runs, {len(manifest['failures'])} failures")
    return 0 if not manifest["failures"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent comparison benchmark runner")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("prepare")
    pilot = sub.add_parser("pilot")
    pilot.add_argument("--repeats", type=int, default=1)
    pilot.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.command == "validate":
        return cmd_validate()
    if args.command == "prepare":
        return cmd_prepare()
    if args.command == "pilot":
        return cmd_pilot(args.repeats, args.seed)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
