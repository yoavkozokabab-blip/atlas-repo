"""One-click entry point for the Agent/Atlas benchmark.

Default behavior is safe: create a 24-run manual pilot queue for the six pilot
tasks, two agents, two Atlas conditions, one repeat.

When provider command environment variables are configured, use --mode auto or
--mode hybrid to execute configured providers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_runner.adapters import AtlasAdapter, NoAtlasAdapter
from benchmark_runner.io import write_json
from benchmark_runner.matrix import AGENTS, build_records, new_run_set_id, write_run_set
from benchmark_runner.models import now_iso
from benchmark_runner.providers import ClaudeProvider, CodexProvider, CursorProvider
from benchmark_runner.tasks import load_repositories, load_tasks


PROVIDERS = {
    "codex": CodexProvider,
    "cursor": CursorProvider,
    "claude": ClaudeProvider,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, help="Repeats per task/condition.")
    parser.add_argument("--task", action="append", help="Limit to task id. Can be repeated.")
    parser.add_argument("--agents", default="codex,cursor", help="Comma-separated agents: codex,cursor,claude.")
    parser.add_argument("--run-set-id", default=None, help="Optional stable run set id.")
    parser.add_argument("--mirror-to-root-runs", action="store_true", help="Also write pending cards under runs/<condition>.")
    parser.add_argument(
        "--mode",
        choices=("manual", "auto", "hybrid"),
        default="manual",
        help="manual creates run cards; auto/hybrid are reserved for configured provider commands.",
    )
    args = parser.parse_args()

    agents = tuple(item.strip() for item in args.agents.split(",") if item.strip())
    bad = sorted(set(agents) - set(("codex", "cursor", "claude")))
    if bad:
        raise SystemExit(f"Unknown agent(s): {', '.join(bad)}")
    if args.repeat < 1:
        raise SystemExit("--repeat must be >= 1")

    tasks = load_tasks(args.task)
    repositories = load_repositories()
    run_set_id = args.run_set_id or new_run_set_id()
    records = build_records(
        tasks=tasks,
        repositories=repositories,
        agents=agents,
        repeats=args.repeat,
        run_set_id=run_set_id,
    )
    run_set_dir = write_run_set(records, run_set_id=run_set_id, mirror_to_root_runs=args.mirror_to_root_runs)
    executed = 0
    left_pending = len(records)
    if args.mode in ("auto", "hybrid"):
        for record in records:
            provider = PROVIDERS[record.runner.agent]()
            if not provider.available():
                if args.mode == "auto":
                    record.status = "technical_failure"
                    record.ended_at = now_iso()
                    record.observations.errors.append(
                        f"{record.runner.agent} provider command is not configured"
                    )
                    write_json(run_set_dir / "runs" / record.condition / f"{record.run_id}.json", record.to_dict())
                continue
            adapter = AtlasAdapter() if record.runner.atlas_enabled else NoAtlasAdapter()
            result = provider.run(
                prompt=record.prompt,
                env=adapter.instructions().environment,
                timeout_seconds=900,
                atlas_enabled=record.runner.atlas_enabled,
            )
            record.status = result.status
            record.response_text = result.response_text
            record.runner = result.runner
            record.observations = result.observations
            record.notes = result.notes
            record.ended_at = now_iso()
            write_json(run_set_dir / "runs" / record.condition / f"{record.run_id}.json", record.to_dict())
            executed += 1
        left_pending = len(records) - executed
    print(f"Created run set: {run_set_id}")
    print(f"Run cards: {len(records)}")
    print(f"Manual sheet: {run_set_dir / 'manual_run_sheet.md'}")
    print(f"Pending JSONL: {run_set_dir / 'pending_runs.jsonl'}")
    if args.mode != "manual":
        print(f"Executed provider runs: {executed}")
        print(f"Left pending/manual: {left_pending}")
        print("Provider env vars: CODEX_BENCH_COMMAND_JSON, CURSOR_BENCH_COMMAND_JSON, CLAUDE_BENCH_COMMAND_JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
