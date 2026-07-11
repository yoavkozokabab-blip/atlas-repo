# Methodology — Agent Comparison Benchmark

## Objective

Measure whether **Atlas MCP materially improves repository understanding** for Codex and Cursor agents — not merely whether Atlas returns extra context.

## Conditions

Four arms, identical prompts and repo state:

1. `codex_no_atlas` — Codex, Atlas MCP disabled
2. `codex_with_atlas` — Codex, Atlas MCP connected
3. `cursor_no_atlas` — Cursor, Atlas MCP disabled
4. `cursor_with_atlas` — Cursor, Atlas MCP connected

### With Atlas

- Atlas MCP connected and available to the agent
- Every Atlas tool call logged
- Do **not** manually paste Atlas output into the user prompt

### Without Atlas

- Atlas MCP disabled
- No Atlas context packets, cached scans, or prior Atlas answers accessible
- Session/context reset before each run

## Pilot automation limitation (important)

**Pilot phase 1** includes an automated **stand-in** execution path for harness validation:

| Condition group | Automated stand-in | Live agent required |
|---|---|---|
| `*_no_atlas` | Read-only repo search baseline (ripgrep + file reads) | Yes — real Codex/Cursor |
| `*_with_atlas` | Direct Atlas MCP tool orchestration | Yes — real Codex/Cursor |

Automated stand-ins use the **same prompts** and **same repo SHAs**, but they are **not** substitutes for live agent sessions. Pilot reports label `execution_backend: automated_stand_in` vs `live_agent`.

Codex CLI was **not available in PATH** during pilot harness execution on this machine. Cursor CLI exists but headless agent automation was not wired in pilot v1.

## Run protocol

For each condition × task × repeat:

1. Reset session/context and repo scan cache
2. Confirm Atlas enabled/disabled per condition
3. Send **exact** prompt text (published in `tasks/`)
4. Record: start/end time, response, tool calls, files opened, Atlas calls, errors, retries
5. Do not intervene unless the tool crashes
6. Technical failures scored as failures

Condition order is randomized per task to reduce warm-cache bias.

## Scoring (0–5 each, 30 points total per task)

1. Correctness
2. Completeness
3. File citation accuracy
4. Evidence quality
5. Hallucination avoidance (5 = no unacceptable hallucinations)
6. Actionability

Deterministic pre-scoring checks:

- Required files mentioned
- Unacceptable hallucinated files penalized
- Negative-control tasks: must deny nonexistent features

Human/blind review can override deterministic scores. Scorer sees anonymous run IDs first (`run_A_001`), condition labels revealed after scoring.

## Primary metrics

- Mean/median total score (0–30)
- Per-dimension means
- Hallucination rate
- Task success rate (score ≥ threshold)
- Latency (mean/median)
- Tool-call count, files inspected
- Failure rate

Report absolute difference and percentage change. **Do not claim statistical significance** from pilot n=6.

## Threats to validity

- **Model nondeterminism** — LLM answers vary run-to-run
- **Cache effects** — repo scan cache, agent session warmth
- **Agent differences** — Codex vs Cursor unlike identical models
- **Incomplete gold standards** — especially on large repos
- **Evaluator bias** — deterministic scorer is partial
- **Repository selection bias** — pilot uses one small fixture + requests
- **MCP overhead** — with-Atlas may be slower despite better answers
- **Stale Atlas context** — scan may not reflect latest commit
- **Automation gap** — pilot stand-ins ≠ real agents

## Publication standard

Safe wording:

> "On this benchmark, Atlas improved X on Y category under Z conditions."

Avoid:

> "Atlas makes coding agents 10x smarter."

Publish: methodology, prompts, repo SHAs, rubric, failures, raw artifacts.

## Full benchmark (post-pilot)

After pilot approval, expand to 24+ tasks across 3 repo tiers (small/medium/large), 3 repeats per task, live agent runs for all four conditions.
