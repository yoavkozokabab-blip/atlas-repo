# Atlas benchmarks

## Retrieval benchmark (the numbers in the main README)

`scripts/bench_audit4_retrieval.py` scores 62 tasks across 11 repositories. The correct
file for each task is decided without Atlas (for symbol tasks: the file that defines
`class X` / `def X`, found by regex), and Atlas is compared with keyword grep and BM25.

To reproduce, clone the ten public repositories into one folder and point the script at
it:

```bash
mkdir -p bench_repos && cd bench_repos
for r in psf/requests pallets/flask fastapi/fastapi pydantic/pydantic Textualize/rich \
         fastapi/typer celery/celery fastapi/sqlmodel django/django langchain-ai/langchain; do
  git clone --depth 1 https://github.com/$r
done
cd ..
ATLAS_BENCH_REPOS=$PWD/bench_repos python scripts/bench_audit4_retrieval.py
```

The 11th suite is Atlas's own `atlas_desktop/` folder. Results vary slightly with the
commit each repository is at. The script prints a summary and writes raw JSON to
`reports/audit4/`.

---

## Repository understanding benchmarks (Phase 130)

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

From `the Atlas repo`:

```powershell
py -3 benchmarks/generate_suite.py
py -3 benchmarks/runner.py
```



## Agent comparison benchmark (Codex/Cursor ± Atlas)

Pilot harness for comparing Codex and Cursor with/without Atlas MCP lives in
`benchmarks/agent_comparison/` (does not replace Phase 130 or Phase 103 work).

```powershell
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py validate
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py prepare
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py pilot
py -3 benchmarks/agent_comparison/scripts/score_results.py --pilot
py -3 benchmarks/agent_comparison/scripts/summarize_results.py --pilot
```

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
