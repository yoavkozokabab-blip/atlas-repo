# Agent/Atlas Repository Understanding Benchmark

This benchmark package compares four agent conditions on repository-understanding tasks:

- `codex_no_atlas`
- `codex_with_atlas`
- `cursor_no_atlas`
- `cursor_with_atlas`

The benchmark is intentionally separated from the existing Phase 130 benchmark files. It lives under
`benchmarks/agent_atlas_comparison/` so older benchmark work is not overwritten.

## Current Status

The pilot harness and six pilot tasks are defined. The new `benchmark_runner/` workflow creates a
24-run paired pilot queue by default and supports manual capture plus heuristic or manual scoring.
Valid pilot measurements still require real Codex and Cursor responses under reset conditions. Do not
treat harness-generated technical failures or pending records as evidence that Atlas helped or hurt.

Atlas MCP availability was checked in the active environment on 2026-07-10. The MCP server was
available, but no repository scan was performed as part of benchmark execution because the no-Atlas
control conditions must not inherit Atlas-generated context.

## Layout

```text
benchmarks/agent_atlas_comparison/
  README.md
  methodology.md
  repositories.json
  tasks/
    task_001.json
    ...
  gold/
    task_001.md
    ...
  runs/
    codex_no_atlas/
    codex_with_atlas/
    cursor_no_atlas/
    cursor_with_atlas/
  scores/
    raw_scores.csv
    summary.csv
  reports/
    environment.json
    benchmark_report.md
    benchmark_report.json
  benchmark_runner/
    providers/
      codex.py
      cursor.py
      claude.py
    adapters/
      atlas.py
      no_atlas.py
  repos/
  scripts/
    capture_run.py
    score_run.py
    run_benchmark.py
    score_results.py
    summarize_results.py
  results/
  run_all.py
```

## Basic Commands

Create the 24-run pilot queue:

```powershell
py -3 benchmarks/agent_atlas_comparison/run_all.py
```

The command writes:

- `results/run_sets/<run_set_id>/manual_run_sheet.md`
- `results/run_sets/<run_set_id>/pending_runs.jsonl`
- `results/run_sets/<run_set_id>/runs/<condition>/*.json`

Capture one completed manual run:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/capture_run.py --existing-run-json path\to\pending.json --response-file path\to\response.txt --elapsed-ms 120000 --model "model name"
```

Score completed runs:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/score_run.py
```

Summarize completed/scored runs:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/summarize_results.py
```

List pilot tasks:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/run_benchmark.py --list
```

Emit pending run records for manual/external execution:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/run_benchmark.py --emit-pending --repeat 1
```

Record a technical failure when a condition cannot be run:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/run_benchmark.py --mark-unavailable --reason "Runner unavailable in this environment" --repeat 1
```

Validate and export scores:

```powershell
py -3 benchmarks/agent_atlas_comparison/scripts/score_results.py
py -3 benchmarks/agent_atlas_comparison/scripts/summarize_results.py
```

## How To Produce A Valid Run

1. Check out the repository at the SHA listed in `repositories.json`.
2. Reset the agent session/context.
3. Enable or disable Atlas according to the condition.
4. Use the exact prompt from the task JSON.
5. Do not add Atlas output manually to the prompt.
6. Save the raw response and observed metadata in the generated run JSON.
7. Score blinded outputs against the matching `gold/task_XXX.md` rubric.

If a runner, MCP server, repo checkout, or agent product is unavailable, record that as a technical
failure. Do not substitute another tool or infer results.

## Future Fully Automated Providers

`run_all.py --mode hybrid` or `--mode auto` can execute provider commands when these environment
variables are configured:

- `CODEX_BENCH_COMMAND_JSON`
- `CURSOR_BENCH_COMMAND_JSON`
- `CLAUDE_BENCH_COMMAND_JSON`

Each value must be a JSON array command. The benchmark prompt is sent on stdin, stdout is captured as
the response, and latency is measured exactly. Tool-call and file-open telemetry remain unavailable
unless the provider command emits or records them separately.
