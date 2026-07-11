"""Create paired benchmark run matrices and manual run sheets."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .adapters import AtlasAdapter, NoAtlasAdapter
from .io import append_jsonl, write_json
from .models import CONDITIONS, RunRecord, condition_name
from .paths import RESULTS_DIR, RUNS_DIR
from .tasks import BenchmarkTask, RepositorySpec

AGENTS = ("codex", "cursor")


def new_run_set_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_records(
    *,
    tasks: list[BenchmarkTask],
    repositories: dict[str, RepositorySpec],
    agents: tuple[str, ...] = AGENTS,
    repeats: int = 1,
    run_set_id: str | None = None,
) -> list[RunRecord]:
    run_set = run_set_id or new_run_set_id()
    records: list[RunRecord] = []
    for task in tasks:
        for repeat in range(1, repeats + 1):
            for agent in agents:
                agent_conditions = [condition_name(agent, atlas) for atlas in (False, True)]
                ordered_conditions = [c for c in task.condition_order if c in agent_conditions]
                for condition in agent_conditions:
                    if condition not in ordered_conditions:
                        ordered_conditions.append(condition)
                for condition in ordered_conditions:
                    atlas_enabled = "_with_atlas" in condition
                    repo = repositories[task.repository_id]
                    records.append(
                        RunRecord.pending(
                            task=task,
                            repo=repo,
                            agent=agent,
                            atlas_enabled=atlas_enabled,
                            repeat=repeat,
                            run_set_id=run_set,
                        )
                    )
    return records


def condition_instructions(atlas_enabled: bool) -> tuple[str, ...]:
    adapter = AtlasAdapter() if atlas_enabled else NoAtlasAdapter()
    return adapter.instructions().checklist


def write_run_set(records: list[RunRecord], *, run_set_id: str, mirror_to_root_runs: bool = False) -> Path:
    run_set_dir = RESULTS_DIR / "run_sets" / run_set_id
    pending_path = run_set_dir / "pending_runs.jsonl"
    manifest = {
        "run_set_id": run_set_id,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "record_count": len(records),
        "conditions": list(CONDITIONS),
        "status": "pending_manual_or_external_run",
        "notes": "Pending records are not benchmark results until a real response is captured.",
    }
    write_json(run_set_dir / "manifest.json", manifest)
    append_jsonl(pending_path, [record.to_dict() for record in records])
    write_manual_sheet(run_set_dir / "manual_run_sheet.md", records)

    for record in records:
        run_path = run_set_dir / "runs" / record.condition / f"{record.run_id}.json"
        write_json(run_path, record.to_dict())
        if mirror_to_root_runs:
            write_json(RUNS_DIR / record.condition / f"{record.run_id}.json", record.to_dict())
    return run_set_dir


def write_manual_sheet(path: Path, records: list[RunRecord]) -> None:
    lines = [
        "# Manual Benchmark Run Sheet",
        "",
        "These are pending run cards. They become valid benchmark data only after a fresh agent",
        "session is used and the full response/telemetry is captured with `scripts/capture_run.py`.",
        "",
    ]
    for idx, record in enumerate(records, start=1):
        lines.extend(
            [
                f"## {idx}. {record.run_id}",
                "",
                f"- Condition: `{record.condition}`",
                f"- Agent: `{record.runner.agent}`",
                f"- Atlas enabled: `{record.runner.atlas_enabled}`",
                f"- Task: `{record.task_id}`",
                f"- Repository: `{record.repository_id}` @ `{record.repository_commit_sha}`",
                f"- Category: `{record.category}`",
                f"- Difficulty: `{record.difficulty}`",
                "",
                "Checklist:",
            ]
        )
        for item in condition_instructions(record.runner.atlas_enabled):
            lines.append(f"- {item}")
        lines.extend(
            [
                "",
                "Prompt:",
                "",
                "```text",
                record.prompt,
                "```",
                "",
                "Capture command template:",
                "",
                "```powershell",
                (
                    "py -3 benchmarks\\agent_atlas_comparison\\scripts\\capture_run.py "
                    f"--run-id {record.run_id} --condition {record.condition} --task-id {record.task_id} "
                    f"--agent {record.runner.agent} "
                    f"{'--atlas-enabled' if record.runner.atlas_enabled else '--no-atlas'}"
                ),
                "```",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def records_to_rows(records: list[RunRecord]) -> list[dict[str, object]]:
    return [asdict(record) for record in records]
