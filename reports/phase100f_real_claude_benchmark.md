# Phase 100F — Real Claude API Benchmark

**Status:** Blocked — `ANTHROPIC_API_KEY` not configured  
**Date:** 2026-06-01  
**Protocol:** Phase 100E task suite (20 tasks) + Phase 100B anchor scoring via live Anthropic API

---

## 1. Executive summary

| Item | Value |
|------|-------|
| Harness | `builder_core/scripts/phase100f_real_claude_benchmark.py` |
| Tasks | 20 (architecture 8, impact 6, repository understanding 6) |
| Arms | Claude Only vs Claude + JARVIS |
| Trials (default CLI) | 1 (`--trials 3` for 100E parity) |
| **API execution** | **Not run** — no key in env or `.env` |
| Phase 100E proxy (simulated) | 3.17× compression, PARTIAL verdict — see `phase100e_context_compression_execution.md` |

The harness is implemented and validated (syntax + Anthropic SDK connectivity). **Real token, latency, and cost metrics require setting `ANTHROPIC_API_KEY` and re-running.**

---

## 2. Summary table (API metrics — pending)

| Metric | Claude Only | Claude + JARVIS | Notes |
|--------|------------:|----------------:|-------|
| Input tokens | — | — | From `usage.input_tokens` per API call |
| Output tokens | — | — | From `usage.output_tokens` |
| Total tokens | — | — | Sum per task × trial |
| Latency (s) | — | — | Wall-clock per task |
| API cost (USD) | — | — | Frozen Sonnet price table × usage |
| Quality (0–4) | — | — | Same anchor rubric as 100E |

---

## 3. How to run (live API)

```bash
cd local_jarvis
pip install anthropic

# Add to .env or shell:
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-sonnet-4-6   # optional

py -3 -m builder_core.cli init --project .
py -3 -m builder_core.scripts.phase100f_real_claude_benchmark --trials 1
```

**Smoke subset:**

```bash
py -3 -m builder_core.scripts.phase100f_real_claude_benchmark --trials 1 --task-ids A1 C6
```

**Full parity with Phase 100E:**

```bash
py -3 -m builder_core.scripts.phase100f_real_claude_benchmark --trials 3
```

**Outputs (after successful run):**

| File | Description |
|------|-------------|
| `reports/phase100f_real_claude_benchmark.md` | This report (overwritten with results) |
| `reports/phase100f_run/raw_trials.json` | Per-run tokens, latency, cost, quality |
| `reports/phase100f_run/task_summary.json` | Medians per task × arm |
| `reports/phase100f_run/verdict.json` | Suite gates |

---

## 4. Harness design (matches Phase 100B / 100E)

| Arm | Tools |
|-----|-------|
| **Claude Only** | `read_file`, `grep`, `list_dir`, `glob`, `submit_answer` |
| **Claude + JARVIS** | Above + `jarvis_ask`, `jarvis_graph_summary`, `jarvis_impact_file`, `jarvis_impact_module` |

- Temperature `0`, max `10` turns per task  
- Same preregistered prompts and anchor quality scoring as Phase 100E  
- No detector or benchmark changes  

---

## 5. Blocker detail

```
ANTHROPIC_API_KEY was not found in the environment or .env files.
```

Checked: process environment, `local_jarvis/.env`, User/Machine Windows environment variables.

---

## 6. Next step

Set a valid Anthropic API key and re-run the command above. The report and `reports/phase100f_run/` artifacts will populate with **real** API measurements.
