# Agent Comparison Benchmark (Pilot)

Rigorous, publishable comparison of repository understanding with and without Atlas MCP:

| Condition | Agent | Atlas MCP |
|---|---|---|
| `codex_no_atlas` | Codex | disabled |
| `codex_with_atlas` | Codex | enabled |
| `cursor_no_atlas` | Cursor | disabled |
| `cursor_with_atlas` | Cursor | enabled |

This directory is **separate** from existing Phase 130 (`benchmarks/runner.py`) and Phase 103 (`builder_core/benchmark_framework/`) work.

## Pilot scope (phase 1)

- 6 tasks (2 retrieval, 1 architecture, 1 impact, 1 debugging, 1 negative control)
- 2 repositories: controlled `atlas_reference` + real `requests` (pinned SHA)
- Automated stand-in runs for harness validation
- Live Codex/Cursor agent runs require manual completion (see methodology)

## Layout

```
agent_comparison/
  README.md
  methodology.md
  repositories.json
  tasks/           # task definitions (JSON)
  gold/            # gold answers + rubric (Markdown)
  runs/            # raw run artifacts per condition
  scores/          # blinded + revealed scores
  reports/         # pilot + full benchmark reports
  scripts/         # run, score, summarize
```

## Quick start

```powershell
cd C:\J.A.R.V.I.S\atlas-rc1-clean

# Validate tasks and gold files
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py validate

# Prepare repos (clone/check SHAs)
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py prepare

# Pilot: automated stand-in runs (NOT live Codex/Cursor agents)
py -3 benchmarks/agent_comparison/scripts/run_benchmark.py pilot --repeats 1

# Score (blinded first, then reveal)
py -3 benchmarks/agent_comparison/scripts/score_results.py --pilot
py -3 benchmarks/agent_comparison/scripts/summarize_results.py --pilot
```

## Principles

- Same prompt text for every condition
- Same repository commit for every condition
- No Atlas hints in control runs
- Failures recorded, never hidden
- No fabricated agent transcripts

See `methodology.md` for full protocol, threats to validity, and publication rules.
