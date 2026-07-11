# Methodology

## Goal

Measure whether Atlas materially improves repository understanding for coding agents. The comparison
must distinguish useful repository understanding from simply returning more context.

## Conditions

| Condition | Agent | Atlas state |
|-----------|-------|-------------|
| `codex_no_atlas` | Codex | Atlas MCP disabled and Atlas context inaccessible |
| `codex_with_atlas` | Codex | Atlas MCP connected and available |
| `cursor_no_atlas` | Cursor | Atlas MCP disabled and Atlas context inaccessible |
| `cursor_with_atlas` | Cursor | Atlas MCP connected and available |

For Atlas-enabled runs, record every Atlas tool call. For no-Atlas runs, do not leave Atlas-generated
files, context packs, cached answers, or copied Atlas output available to the agent.

## Repositories

The pilot uses one controlled local repo and three real open-source repos:

- Controlled small repo: `controlled_atlas_reference`, 27 files, source-controlled inside this Atlas checkout.
- Small/medium real repo: Requests.
- Medium real repo: FastAPI.
- Large real repo: Home Assistant Core.

Exact SHAs and observed tree counts are in `repositories.json`.

## Pilot Tasks

The pilot has six tasks:

- 1 retrieval task
- 1 cross-file reasoning task
- 1 architecture task
- 1 impact task
- 1 debugging task
- 1 negative-control task

The full benchmark should expand to at least 24 tasks, balanced across repository size, difficulty,
and task category.

## Prompt Discipline

Each task JSON contains the exact prompt. The prompt must be copied verbatim into every condition.
Do not add hints, file paths, Atlas context, stack-trace clarifications, or evaluator expectations
to one condition and not the others.

## Run Protocol

For each task and condition:

1. Reset the session/context.
2. Confirm the Atlas state required by the condition.
3. Confirm the repository checkout SHA.
4. Start timing.
5. Submit the exact task prompt.
6. Do not intervene unless the runner technically crashes.
7. Stop timing when the final answer is available.
8. Record response text, tool calls, Atlas calls, files opened, errors, retries, latency, and token
   usage when available.
9. If the run fails technically, record it as a technical failure.

The preferred repeat count is 3 per task and condition. If repeats are infeasible, record the lower
count and explain why.

## Semi-Automated Execution

Use `run_all.py` to create a run set. The default run set has:

- 6 tasks
- 4 conditions
- 1 repeat
- 24 pending run cards

When no provider command is configured, the run cards are manual protocol cards. The operator must run
the agent in a fresh session, paste the exact prompt, save the full response, and capture telemetry
with `scripts/capture_run.py`.

When a provider command is configured with `*_BENCH_COMMAND_JSON`, `run_all.py --mode hybrid` can run
that provider automatically. The prompt is passed on stdin and stdout is treated as the complete
answer. The framework records latency exactly and token counts as estimated unless the provider exposes
exact usage.

## Blinding

Run records include an `anonymous_id`. Scorers should use blinded packets that omit condition labels
until scoring is complete. If a response self-identifies Atlas usage, note the blinding limitation.

## Scoring

Each task is scored on six 0-5 dimensions:

| Dimension | Meaning |
|-----------|---------|
| Correctness | The answer resolves the core question accurately. |
| Completeness | The answer covers required behaviors and caveats. |
| File citation accuracy | Cited files/functions support the claims. |
| Evidence quality | Reasoning is grounded in repository evidence. |
| Hallucination avoidance | The answer avoids invented files, APIs, or behavior. |
| Actionability | The answer is useful for a developer deciding what to inspect or change. |

Maximum score per task: 30.

Technical failures are reported in failure-rate metrics. They should not be silently converted into
model-quality scores unless the report explicitly says failures are counted as zero.

The deterministic scorer in `scripts/score_run.py` is `heuristic_v1`. It measures required-file
coverage, obvious hallucination signatures from the gold file, section completeness, and evidence
markers. It is suitable for triage. Public claims should use manual adjudication or reviewed scores.

## Metrics

Primary metrics:

- mean and median total score
- correctness score
- citation accuracy
- hallucination rate
- task success rate
- average and median latency
- tool-call count
- files inspected
- technical failure rate

Secondary metrics:

- category breakdown
- repository-size breakdown
- difficulty breakdown
- Atlas wins, regressions, and no-effect cases
- Codex deltas with/without Atlas
- Cursor deltas with/without Atlas

Do not claim statistical significance from this pilot. The pilot is for fairness and harness
validation.

## Atlas Impact Thresholds

- Strong win: accuracy +15 percentage points or more, or same accuracy with 30%+ less time/tokens.
- Moderate win: accuracy +5 to +14.999 points, or same accuracy with meaningful efficiency gain.
- No meaningful difference: accuracy delta within +/-5 points and no large time/token delta.
- Moderate regression: accuracy -5 to -14.999 points, or 30%+ more time/tokens without quality gain.
- Strong regression: accuracy -15 points or worse.

## Fairness Checks

Before publishing any result, verify:

- same prompt wording
- same repository SHA
- same model/tool version where possible
- same system instructions where possible
- no Atlas-generated hints in no-Atlas runs
- no hidden manual steering
- no different timeout limits
- no cherry-picking successful runs
- randomized condition order per task

## Threats To Validity

- Model nondeterminism can dominate small pilots.
- Caches can leak repo knowledge between runs.
- Cursor and Codex have different tool surfaces and defaults.
- Atlas MCP overhead can improve evidence but increase latency.
- Gold standards can be incomplete or wrong.
- Evaluator bias remains if blinding is incomplete.
- Repo selection can favor or penalize Atlas.
- Atlas context can be stale relative to pinned repo SHAs.
- Counting files inspected is approximate unless the runner exposes exact telemetry.

## Publication Rule

A public claim must use wording like:

> On this benchmark, Atlas improved X on Y category under Z conditions.

Avoid unsupported claims such as:

> Atlas makes coding agents 10x smarter.
