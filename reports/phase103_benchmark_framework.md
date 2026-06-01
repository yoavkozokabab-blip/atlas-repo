# Phase 103: Benchmark Framework for JARVIS vs Codex Alone

## Status

Implemented as an additive, offline package under `builder_core/benchmark_framework/`.
It does not call Claude, Codex, OpenAI, or any other external API. No API key is
required.

## Comparison Arms

| Mode | Purpose |
|---|---|
| `codex_alone` | Run a prompt in a fresh Codex session using ordinary read-only repository inspection. |
| `jarvis_plus_codex` | Run the paired prompt in a fresh Codex session with deterministic local JARVIS context precomputed by Builder Core. |

## Task Corpus

`builder_core/benchmark_framework/data/benchmark_tasks_v1.json` contains 20
initial tasks for `local_jarvis`. The corpus covers:

- repository understanding
- dependency analysis
- impact analysis
- architectural risk
- contract analysis
- verification evidence
- confirmed defect detection
- fix planning

Each task stores:

```text
task_id
repo_id
repo_path
task_type
prompt
expected_answer
scoring_rubric
required_evidence
baseline_mode
jarvis_mode
```

## Generate A Run Package

```powershell
py -3 -m builder_core.benchmark_framework.cli validate
py -3 -m builder_core.benchmark_framework.cli generate --run-id phase103_manual_01
```

The generator writes paired prompts, editable run-log templates, editable score
templates, and a manifest under:

```text
reports/benchmarks/<run-id>/
```

Generated run packages are intentionally gitignored. They are local evaluation
artifacts, not source files.

## Manual Run Logging

Run each prompt in a fresh Codex session, save the answer, then record the run:

```powershell
py -3 -m builder_core.benchmark_framework.cli record-run `
  --run-dir reports/benchmarks/phase103_manual_01 `
  --task-id ru01_subsystems `
  --mode codex_alone `
  --model-tool-used "Codex desktop" `
  --start-time 2026-06-01T10:00:00 `
  --end-time 2026-06-01T10:02:30 `
  --answer-file C:\Temp\ru01_codex_alone.txt
```

Repeat with `--mode jarvis_plus_codex`.

Run logs store:

- model/tool used
- mode
- start and end time
- elapsed seconds
- estimated input and output tokens
- raw answer path
- score path
- notes

## Token Estimates

The framework uses a dependency-free `characters / 4` estimator. Every generated
log and report explicitly labels token numbers as estimates. `record-run`
accepts `--estimated-input-tokens` and `--estimated-output-tokens` as manual
overrides when a trusted UI provides a better count.

## Manual Scoring

Score each answer after review:

```powershell
py -3 -m builder_core.benchmark_framework.cli score `
  --run-dir reports/benchmarks/phase103_manual_01 `
  --task-id ru01_subsystems `
  --mode codex_alone `
  --correctness 4 `
  --evidence-quality 4 `
  --completeness 4 `
  --hallucination-risk 1 `
  --task-success yes
```

The four quality dimensions use a `0..5` scale. Lower hallucination risk is
better. Confirmed-defect tasks can additionally record `--true-positives`,
`--false-positives`, and `--false-negatives`.

## Summary

```powershell
py -3 -m builder_core.benchmark_framework.cli summary `
  --run-dir reports/benchmarks/phase103_manual_01
```

This writes:

```text
summary.json
summary.md
```

The summary reports:

- Codex Alone vs JARVIS + Codex win/loss/tie
- average estimated token reduction
- average speedup
- average quality delta
- task-success rate
- bug-finding precision and recall
- per-task breakdown

## Safety Boundaries

- Offline only.
- Read-only against target repositories.
- No detector changes.
- No benchmark behavior changes in the existing Builder Core engine.
- No router, browser, voice, trading, or website changes.
- Generated packages remain local under `reports/benchmarks/`.

## Verification

Executed on June 1, 2026:

```powershell
py -3 -m builder_core.benchmark_framework.cli validate
py -3 -m builder_core.benchmark_framework.cli generate --run-id phase103_smoke --skip-jarvis-context
py -3 -m builder_core.benchmark_framework.cli summary --run-dir reports\benchmarks\phase103_smoke
py -3 -m builder_core.benchmark_framework.cli generate --run-id phase103_context_smoke
py -3 -m pytest builder_core\tests\test_phase103_benchmark_framework.py -q -p no:cacheprovider --basetemp .pytest_tmp\phase103_targeted
py -3 -m pytest builder_core\tests\ -q -p no:cacheprovider --basetemp .pytest_tmp\phase103_builder_core
```

Results:

- Task corpus validation: `21 benchmark task(s)`, all valid.
- Package generation without precomputed context: passed.
- Fresh incomplete-package summary: passed; incomplete score templates are reported and skipped.
- Package generation with real local JARVIS context: passed; no API access.
- Focused Phase 103 tests: `10 passed`.
- Builder Core regression suite: `410 passed`.

The real local-context generation smoke took approximately 5.6 minutes on this
large checkout. The framework exposes `--skip-jarvis-context` for package-shape
smokes while preserving full local-context generation for actual comparisons.
