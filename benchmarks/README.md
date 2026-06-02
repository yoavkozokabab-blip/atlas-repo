# Atlas Repository Understanding Benchmarks (Phase 130)

Measure Atlas **Build Plan**, **Investigate**, and **Impact Analysis** quality against ground-truth scenarios — not internal unit tests alone.

## Layout

```
benchmarks/
  atlas_benchmark_suite_v1.json   # 51 scenarios (50 required + 1 optional)
  repos/atlas_reference/          # Reference repository with known structure
  schema.py                       # Scenario + result models
  evaluator.py                    # Metrics + Atlas score
  runner.py                       # Run suite + generate report
  generate_suite.py               # Regenerate repos + JSON
  competitive/manual_comparison_template.md
  results/latest_run.json         # Last run output (generated)
```

## Run validation

From `local_jarvis`:

```powershell
py -3 benchmarks/generate_suite.py
py -3 benchmarks/runner.py
```

Report: `reports/phase130_repository_understanding_validation.md`

## Metrics

| Metric | Definition |
|--------|------------|
| File precision | \|recommended ∩ expected\| / \|recommended\| |
| File recall | \|expected found in recommended\| / \|expected\| |
| Insertion accuracy | recommended insertion matches expected path |
| Knowledge accuracy | expected concept_id matched |
| Evidence accuracy | repository_evidence supports findings |
| Risk / test recall | keyword overlap with expected lists |

**Atlas score** — weighted by category (feature / investigate / impact).

## Categories

- **20+** feature additions
- **20+** bug investigations
- **10+** impact analyses

## Optional external repo

`opt_final_algo_ema` targets `FINAL_ALGO_TRADER` when present on disk; skipped by default in CI.

## Principles

- No new intelligence systems in this phase
- No UI or styling changes
- Benchmark failures drive future work
