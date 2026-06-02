# Phase 104: Token Accounting and Context Compression Hardening

**Status:** Design only  
**Date:** 2026-06-01  
**Scope:** Phase 103 benchmark framework and current Builder Core `ask` context generation  
**Constraint:** No production implementation, no detector changes, no new benchmark tasks

## 1. Executive Summary

Phase 103 is a useful offline comparison harness, but it cannot yet prove that
`jarvis_plus_codex` reduces the tokens a developer spends to complete a task.
It currently estimates the initial pasted prompt package and the saved final
answer. It does not account for the rest of a Codex session: repository reads,
tool outputs, replayed history, follow-up prompts, or peak visible context.

The first full Phase 103 manual package exposes a second issue: JARVIS context is
often longer and less targeted than it needs to be. Across 21 tasks:

| Metric | Value |
|---|---:|
| `codex_alone` initial prompt package | 3,143 estimated tokens total |
| `jarvis_plus_codex` initial prompt package | 13,564 estimated tokens total |
| Embedded JARVIS context | 9,963 estimated tokens total |
| Extra JARVIS wrapper text beyond baseline and context | 458 estimated tokens total |
| Average embedded JARVIS context | 474.4 estimated tokens per task |
| Initial JARVIS-to-baseline prompt ratio | 4.316x |

This does **not** mean JARVIS loses the end-to-end comparison. The intended gain
is that a useful JARVIS packet avoids many later repository reads. It does mean
that Phase 104 must measure the whole visible session and reduce unnecessary
packet cost before making a product claim.

The shortest safe path is:

1. Finish transparent accounting for every visible token-bearing component.
2. Add a deterministic compact fact-packet renderer.
3. Preserve evidence references and caveats while removing repeated prose.
4. Fix relevance leaks that place unrelated repository corpus files into
   architecture context.
5. Compare `codex_alone`, current prose packets, and compact packets on the
   existing frozen Phase 103 tasks.

## 2. Audit Snapshot

### 2.1 Baseline inspected

The measured package is:

```text
reports/benchmarks/phase103_manual_20260601_184247/
```

It was generated from the committed Phase 103 framework. Measurements in this
report use the same estimator as Phase 103:

```text
estimated_tokens = ceil(character_count / 4)
```

### 2.2 Concurrent Phase 104A note

During this read-only audit, Phase 104A-shaped work appeared in the worktree and
was committed independently as:

```text
215995eb Phase 104A: token accounting instrumentation for benchmark run packages
```

That commit changes:

```text
builder_core/benchmark_framework/tokens.py
builder_core/benchmark_framework/runner.py
builder_core/benchmark_framework/schema.py
builder_core/benchmark_framework/cli.py
builder_core/benchmark_framework/summary.py
builder_core/tests/test_phase104a_token_accounting.py
```

Phase 104A adds a useful first breakdown:

```text
raw_prompt
jarvis_context
final_prompt_package
answer_text
```

It was not authored, modified, or approved by this design pass. It is incomplete
for full Phase 104 because it does not yet break JARVIS context into sections,
account for visible tool/session traffic, measure peak context, or solve context
relevance.

## 3. Where Tokens Are Currently Spent

### 3.1 Embedded JARVIS context

The 9,963 estimated tokens embedded across the first manual package divide as
follows:

| Context section | Estimated tokens | Share |
|---|---:|---:|
| `EVIDENCE` | 4,903 | 49.2% |
| `ANSWER` prose | 3,032 | 30.4% |
| `SOURCES` | 1,197 | 12.0% |
| `ASK_QUALITY` | 546 | 5.5% |
| Section labels and `MODE` | 285 | 2.9% |
| **Total** | **9,963** | **100.0%** |

Evidence prose is the largest spend. It often repeats facts already present in
the answer and paths already present in `SOURCES`.

### 3.2 Largest current packets

| Task | Embedded context tokens | Main cause |
|---|---:|---|
| `impact01_config` | 808 | Full architectural-risk ranking instead of targeted config impact |
| `risk01_ranking` | 808 | 12 ranked modules plus repeated score breakdown evidence |
| `risk02_centrality_vs_risk` | 808 | Same full ranking packet as `risk01_ranking` |
| `verify01_evidence_types` | 741 | Retrieval chunks and repeated source paths |
| `ru01_subsystems` | 611 | Polluted subsystem selection and long snippets |
| `defect02_bfs_queue` | 582 | Retrieval chunks instead of fixture-specific defect facts |
| `ru03_voice_path` | 580 | Retrieval excerpts rather than a compact path packet |
| `defect01_wrong_operator` | 525 | Generic Builder Core README retrieval instead of fixture comparison |

### 3.3 Session tokens not currently accounted for

Phase 103 records `estimated_input_tokens` from the generated prompt package and
`estimated_output_tokens` from the saved answer. That misses:

- visible system or benchmark scaffold text;
- tool definitions shown to the agent;
- follow-up user prompts;
- Codex tool-call arguments;
- file reads, grep results, directory listings, and other tool output;
- repeated history carried into later turns;
- peak visible context size;
- context-generation latency;
- one-time index-build latency;
- whether a token number was estimated, manually overridden, or observed in a
  trusted UI.

Hidden platform tokens cannot be measured without provider support. Phase 104
must not pretend otherwise. It should measure the visible, reproducible surface
and label it clearly.

## 4. Redundancy and Relevance Findings

### 4.1 Repeated answer, evidence, and source text

Current `default_jarvis_context()` serializes:

```text
MODE
ANSWER
up to 12 EVIDENCE lines
up to 12 SOURCES
ASK_QUALITY percentages
```

For architectural risk, the answer lists 12 ranked modules with score
breakdowns. Evidence then repeats the ranking and individual score components.
Sources repeat module paths already named in the ranking.

The first package contains:

| Item | Count |
|---|---:|
| Nonblank context lines | 520 |
| Evidence lines | 128 |
| Source lines | 121 |
| Repeated line occurrences, including structural metadata | 434 |
| Distinct repeated line values | 97 |

Some repeated lines are harmless headers. Others are real waste. For example,
the risk packet repeats the same imported-test evidence line multiple times.

### 4.2 Identical packets for semantically different tasks

Two duplicate packet groups show that routing specificity is not strong enough:

| Identical packet size | Tasks |
|---:|---|
| 808 tokens | `impact01_config`, `risk01_ranking`, `risk02_centrality_vs_risk` |
| 401 tokens | `impact03_contract_facts`, `plan01_config`, `risk03_cycles` |

It can be valid for related questions to share facts. It is not acceptable to
inject the same full packet by default when the developer asked for a targeted
impact, risk, contract, cycle, or fix-planning answer.

### 4.3 Repository corpus pollution

`ru01_subsystems` says the `data` subsystem is the primary production area and
cites files under:

```text
data/real_repo_corpus/phase98a/
```

The cause is structural:

- `classify_file_role()` treats code files under `data/` as
  `production_code`; its dataset branch is limited to data-like extensions.
- `discover_subsystems()` groups those files into top-level subsystem `data`.
- `production_subsystems()` includes any subsystem with production-code files.
- `_architecture_sources()` then accepts those paths because their role is
  incorrectly `production_code`.

This is not merely a token issue. It lowers context quality while making the
`ASK_QUALITY` production percentage look healthier than it is.

### 4.4 Generic retrieval where structured facts exist

Several task contexts fall back to keyword retrieval and copy long chunks from
`builder_core/README.md` or docstrings. Examples include the wrong-operator
fixture and Builder Core map tasks. The output is locally grounded, but it is
not the smallest task-specific proof packet.

## 5. Are Ranking and Evidence Outputs Too Verbose?

Yes.

`architectural_risk.format_ranking_answer()` renders every top module and every
score component as prose. `format_ranking_evidence()` then repeats score
breakdowns and diagnostics. This is useful for a terminal report but expensive
as an injected agent context.

The same distinction applies elsewhere:

| Surface | Human display need | Agent context need |
|---|---|---|
| Architectural risk ranking | Detailed prose, top 12, diagnostics | Top 3 to 5 facts, stable references, caveats |
| Impact analysis | Full file/module/path report | Target, direct/transitive counts, top proven edges, unresolved count |
| Repository architecture | Readable subsystem descriptions | Compact subsystem rows, role, entry paths, dependencies |
| Retrieval fallback | Extractive snippets | Deduped references and short excerpts only |
| Verification evidence | Review packet detail | Evidence atom types, strengths, refs, blockers |

Human terminal formatters should remain available. Agent injection should use a
separate compact renderer.

## 6. Compact Machine-Readable Fact Packets

### 6.1 Principle

Do not compress by deleting uncertainty. Compress by encoding stable facts once.

The injected packet should be deterministic, machine-readable, and small enough
for an agent to scan. Expanded human-readable reports remain available as
sidecars for inspection.

### 6.2 Proposed compact packet format

Use one compact JSON object with documented short keys:

```json
{
  "v": 1,
  "mode": "impact",
  "target": "builder_core/bug_intelligence/engine.py",
  "facts": [
    {"k": "impact", "direct": 8, "transitive": 3, "risk": "low", "confidence": "unknown"},
    {"k": "unverified", "count": 78}
  ],
  "refs": [
    {"id": "r1", "p": "builder_core/bug_intelligence/engine_benchmark.py", "l": 210}
  ],
  "caveats": ["impact_may_be_incomplete"],
  "srcq": {"prod": 100, "arch": 0, "report": 0, "bench": 0},
  "truncated": false
}
```

For architectural risk:

```json
{
  "v": 1,
  "mode": "architectural_risk",
  "facts": [
    {"k": "risk", "p": "config.py", "rank": 1, "score": 212.8, "fanin": 206, "fanout": 6, "loc": 2181},
    {"k": "risk", "p": "core/logger.py", "rank": 2, "score": 145.0, "fanin": 144, "loc": 26}
  ],
  "refs": [{"id": "r1", "p": "config.py"}],
  "caveats": [],
  "truncated": {"facts_total": 12, "facts_emitted": 5}
}
```

For verification evidence:

```json
{
  "v": 1,
  "mode": "verification",
  "subject": "finding-id",
  "facts": [
    {"k": "evidence", "type": "contract_violation", "strength": "E3", "ref": "r1"},
    {"k": "blocker", "type": "missing_runtime_reproduction"}
  ],
  "refs": [{"id": "r1", "p": "path/to/file.py", "l": 42}],
  "caveats": ["review_lead_only"]
}
```

### 6.3 Packet rules

- Emit each source reference once and refer to it by ID.
- Prefer stable paths and line numbers over copied paragraphs.
- Preserve uncertainty, truncation, degraded-state, unresolved-edge, and
  non-promotion caveats.
- Use task-specific facts. Do not emit a generic top-12 ranking for a targeted
  config-impact question.
- Default to top 3 to 5 facts and top 3 to 5 references.
- Include a sidecar path for expanded detail when more evidence exists.
- Never inject preregistered `expected_answer` text into a benchmark prompt.
- Never use an LLM to compress the packet.

### 6.4 Initial packet budgets

These are design gates, not proof that quality will hold:

| Packet class | Soft target | Hard cap |
|---|---:|---:|
| Impact | 160 tokens | 250 tokens |
| Architectural risk | 250 tokens | 400 tokens |
| Repository understanding | 250 tokens | 400 tokens |
| Dependency analysis | 220 tokens | 350 tokens |
| Contract and verification | 280 tokens | 450 tokens |
| Retrieval fallback | 250 tokens | 400 tokens |

When a packet exceeds its cap, the renderer must truncate deterministically and
emit counts plus an expanded sidecar reference.

## 7. Token Accounting Data Model

### 7.1 Artifact layout

Each task and mode should gain:

```text
token_accounting.<mode>.json
session_events.<mode>.jsonl
context_packet.<mode>.json
context_packet.<mode>.expanded.json
```

The expanded packet is optional for empty or already-small results.

### 7.2 Accounting schema

```json
{
  "schema_version": 1,
  "estimator": {
    "name": "chars_per_4",
    "version": "phase104-v1",
    "all_numbers_estimated": true
  },
  "task_id": "impact02_engine",
  "mode": "jarvis_plus_codex",
  "repo_commit": "<sha>",
  "task_set_hash": "<sha256>",
  "context_formatter_version": "fact-packet-v1",
  "generation": {
    "index_cache": "hit",
    "index_build_elapsed_seconds": 0.0,
    "context_generation_elapsed_seconds": 0.42
  },
  "visible_input": {
    "task_prompt": {"chars": 128, "estimated_tokens": 32},
    "mode_scaffold": {"chars": 420, "estimated_tokens": 105},
    "jarvis_context_total": {"chars": 744, "estimated_tokens": 186},
    "jarvis_context_sections": {
      "facts": {"chars": 420, "estimated_tokens": 105},
      "refs": {"chars": 180, "estimated_tokens": 45},
      "caveats": {"chars": 92, "estimated_tokens": 23},
      "quality": {"chars": 52, "estimated_tokens": 13}
    },
    "tool_definitions": {"chars": 0, "estimated_tokens": 0},
    "tool_arguments": {"chars": 0, "estimated_tokens": 0},
    "tool_results": {"chars": 0, "estimated_tokens": 0},
    "history_replayed": {"chars": 0, "estimated_tokens": 0},
    "final_prompt_package": {"chars": 1292, "estimated_tokens": 323}
  },
  "visible_output": {
    "answer": {"chars": 0, "estimated_tokens": 0}
  },
  "session": {
    "turn_count": 0,
    "tool_call_count": 0,
    "peak_visible_context_tokens": 0,
    "total_visible_input_tokens": 0,
    "total_visible_output_tokens": 0
  },
  "manual_overrides": [],
  "notes": []
}
```

### 7.3 Session event schema

Use append-only JSONL for manually captured visible traffic:

```json
{"seq":1,"kind":"user_prompt","chars":1292,"estimated_tokens":323}
{"seq":2,"kind":"tool_call","tool":"read_file","chars":46,"estimated_tokens":12}
{"seq":3,"kind":"tool_result","tool":"read_file","chars":8812,"estimated_tokens":2203}
{"seq":4,"kind":"assistant_answer","chars":1240,"estimated_tokens":310}
```

This supports manual capture without external APIs. If Codex does not expose a
machine-readable transcript, the operator can record tool-result files and
manual totals. Missing fields stay explicitly `unknown`; they are never silently
treated as zero.

## 8. Exact Metrics to Log

### 8.1 Required per task, mode, and trial

| Metric | Reason |
|---|---|
| Raw task prompt characters and estimated tokens | Frozen task cost |
| Mode scaffold characters and estimated tokens | Harness overhead |
| JARVIS context characters and estimated tokens | Injection cost |
| JARVIS section tokens: facts, refs, caveats, quality, prose fallback | Compression diagnosis |
| Final pasted prompt characters and estimated tokens | Initial visible input |
| Visible tool-definition tokens | Agent tool availability cost |
| Visible tool-call argument tokens by tool | Interaction overhead |
| Visible tool-result tokens by tool | Main source of repository context growth |
| Follow-up prompt tokens | Manual interaction cost |
| History-replayed tokens by turn | Multi-turn accumulation |
| Final answer characters and estimated tokens | Output cost |
| Total visible input tokens | Primary efficiency denominator |
| Total visible output tokens | Output comparison |
| Total visible tokens | Secondary comparison |
| Peak visible context tokens | Context-window pressure |
| Tool calls by type | Explains where savings come from |
| Wall-clock task latency | User-facing speed |
| Context-generation latency | JARVIS overhead |
| Index cache hit/miss and one-time build latency | Amortization |
| Manual override value and source | Auditability |
| Quality score and hallucination risk | Prevents cheap-but-wrong claims |

### 8.2 Derived metrics

| Metric | Formula |
|---|---|
| Initial prompt expansion | `JARVIS initial prompt / baseline initial prompt` |
| End-to-end visible input reduction | `1 - JARVIS visible input / baseline visible input` |
| Tool-result reduction | `1 - JARVIS tool-result tokens / baseline tool-result tokens` |
| Output-token reduction | `1 - JARVIS answer tokens / baseline answer tokens` |
| Peak-context reduction | `1 - JARVIS peak visible context / baseline peak visible context` |
| Speedup | `baseline elapsed / JARVIS elapsed` |
| Quality delta | `JARVIS quality - baseline quality` |
| Quality per 1k visible tokens | `quality / (visible total tokens / 1000)` |
| Context payload efficiency | `quality / JARVIS context packet tokens` |
| Index break-even task count | `one-time index build cost / median per-task savings` |

Do not mix index-build CPU work with model-token counts. Report index latency and
disk/scan work separately. If a token-equivalent proxy is useful, label it as a
separate proxy and never add it to visible model input.

## 9. Offline Token Estimation

### 9.1 Primary estimator

Keep the dependency-free `ceil(chars / 4)` estimator as the primary offline
metric because it is deterministic, cheap, and available for both arms.

Every value must include:

```text
estimated_tokens
character_count
estimator_name
estimator_version
source = estimated | manual_override | observed_ui
```

### 9.2 Manual and observed values

If Codex exposes a trusted token count in the UI, store it separately:

```json
{
  "estimated_tokens": 323,
  "observed_tokens": 337,
  "observed_source": "codex_ui_manual_entry"
}
```

Do not overwrite an estimate invisibly. Preserve both values so results remain
reproducible when the UI count is unavailable.

### 9.3 Sensitivity analysis

Because code punctuation and JSON do not tokenize exactly like prose, the final
report should show a sensitivity band:

```text
lower estimate = ceil(chars / 4.5)
primary estimate = ceil(chars / 4.0)
upper estimate = ceil(chars / 3.5)
```

The comparison is credible only if the direction of the result survives that
band.

## 10. Context Compression Strategy

### 10.1 Stage A: Accounting first

Complete visible token accounting without changing injected context. This gives
a stable baseline and keeps instrumentation changes separate from behavior
changes.

### 10.2 Stage B: Relevance hardening

Before compressing output, stop irrelevant context from entering packets:

- exclude `data/real_repo_corpus/**` from production subsystem discovery;
- preserve its benchmark/dataset role even when files contain source code;
- prevent architecture retrieval from elevating corpus code as JARVIS product
  architecture;
- add a task-specific routing assertion for impact, risk, dependency, contract,
  verification, and fixture-comparison prompts;
- report routing mode and packet kind in the accounting artifact.

### 10.3 Stage C: Deterministic fact packets

Add compact renderers by packet class:

```text
architecture
dependency
impact
architectural_risk
contract
verification
fixture_comparison
retrieval_fallback
```

Keep current human prose formatters unchanged. The benchmark runner should
request compact packets for agent injection.

### 10.4 Stage D: Deduplication and caps

- Deduplicate references by `(path, line)`.
- Deduplicate evidence atoms by stable ID.
- Avoid repeating facts in both answer prose and evidence.
- Emit only task-relevant top facts.
- Add deterministic truncation metadata.
- Keep expanded sidecars for audit.

### 10.5 Stage E: Comparison

Use the same 21 frozen Phase 103 tasks. Do not add tasks during Phase 104.

Run three arms:

| Arm | Purpose |
|---|---|
| `codex_alone` | Product comparison baseline |
| `jarvis_plus_codex_prose` | Current Phase 103 context baseline |
| `jarvis_plus_codex_compact` | Phase 104 compressed packet candidate |

The product headline still compares `codex_alone` vs
`jarvis_plus_codex_compact`. The internal prose arm proves whether the compact
renderer itself reduced cost without hiding a quality regression.

## 11. Comparison Report Format

```markdown
# Token Efficiency Comparison

## Reproducibility
- repo commit
- task-set hash
- formatter version
- estimator version
- trial count

## Aggregate
| Metric | Codex Alone | JARVIS Prose | JARVIS Compact |
|---|---:|---:|---:|
| visible input tokens | | | |
| visible output tokens | | | |
| peak visible context | | | |
| tool-result tokens | | | |
| latency seconds | | | |
| quality score | | | |
| hallucination risk | | | |

## Compression
| Metric | Alone vs Compact | Prose vs Compact |
|---|---:|---:|
| visible input reduction | | |
| peak-context reduction | | |
| context-packet reduction | | |
| speedup | | |
| quality delta | | |

## Per Task
| Task | Packet kind | Packet tokens | Tool-result tokens | Total visible tokens | Quality | Caveats |
|---|---|---:|---:|---:|---:|---|

## Accounting Coverage
- known visible tokens
- unknown or manually entered tokens
- index-build latency
- context-generation latency
```

## 12. How to Prove Token Reduction

Phase 104 can support a defensible token-reduction claim only when all of the
following hold:

1. Freeze repository commit, task-set hash, formatter version, estimator
   version, and run instructions.
2. Use fresh Codex sessions for paired arms.
3. Record the complete visible session, not just the initial pasted prompt.
4. Keep hidden platform context explicitly out of scope.
5. Report estimate provenance and sensitivity bands.
6. Measure one-time index-build latency separately and report amortization.
7. Run the current prose packet and compact packet against the same tasks.
8. Preserve quality scoring, task success, evidence quality, completeness, and
   hallucination risk.
9. Fail the claim if compact packets remove caveats, misroute questions, or
   increase unsupported answers.
10. Report per-task regressions rather than hiding them inside an average.

The existing Phase 100E proxy remains useful historical evidence: it reported
`3.168x` tool-result compression and quality delta `-0.15`. It is not sufficient
proof for Phase 103 because it used a different harness and simulated context
delivery rather than manually completed Codex sessions.

## 13. Likely Files for a Future Implementation

No files are changed by this design except this report. A future implementation
should remain additive and narrowly scoped.

| File | Expected change |
|---|---|
| `builder_core/benchmark_framework/tokens.py` | Complete estimator metadata, section breakdown, sensitivity bands, and session totals |
| `builder_core/benchmark_framework/schema.py` | Add accounting and session-event schemas with backwards-compatible parsing |
| `builder_core/benchmark_framework/runner.py` | Emit compact packets, expanded sidecars, formatter version, and generation latency |
| `builder_core/benchmark_framework/cli.py` | Record visible session events and manual/observed token overrides |
| `builder_core/benchmark_framework/summary.py` | Report full visible-session reductions and accounting coverage |
| `builder_core/benchmark_framework/context_packet.py` | New deterministic compact fact-packet renderer |
| `builder_core/repository_understanding.py` | Correct corpus-code role handling for architecture context |
| `builder_core/retrieval.py` | Keep corpus paths out of architecture packet selection |
| `builder_core/ask.py` | Expose structured task-specific facts without removing current prose answers |
| `builder_core/tests/test_phase104_token_accounting.py` | Accounting reconciliation and backwards compatibility |
| `builder_core/tests/test_phase104_context_packets.py` | Packet caps, dedupe, caveat retention, task specificity, and corpus exclusion |

Legacy prose formatters and existing benchmark tasks should remain intact.

## 14. Acceptance Criteria

### 14.1 Accounting

- Every generated prompt has a `token_accounting.<mode>.json`.
- Every token-bearing section records characters, estimated tokens, estimator
  version, and provenance.
- Section totals reconcile to final visible prompt totals within rounding.
- Manual overrides preserve both estimated and observed values.
- Missing session fields are `unknown`, never silently zero.
- Index-build and context-generation latency are recorded separately.

### 14.2 Compression

- Median compact JARVIS packet is at least 35% smaller than current prose packet.
- No compact packet exceeds its class hard cap without deterministic truncation
  metadata and an expanded sidecar.
- `EVIDENCE` and `SOURCES` are deduplicated.
- Caveats, unresolved edges, degraded states, and non-promotion rules survive
  compression.
- No `data/real_repo_corpus/**` file appears as a product subsystem or
  architecture source.
- Semantically different Phase 103 prompts do not silently receive identical
  generic packets unless the renderer records why the same facts apply.

### 14.3 Proof

- Run all existing 21 Phase 103 tasks without adding tasks.
- Compare `codex_alone`, prose JARVIS, and compact JARVIS.
- Report visible input, visible output, peak visible context, tool-result
  tokens, latency, quality, and hallucination risk per task.
- Claim token reduction only if compact JARVIS reduces total visible input while
  preserving quality and task success.
- Keep detector, promotion, router, browser, voice, trading, and website code
  untouched.

## 15. Recommendation

Proceed with Phase 104 in two separately reviewable passes:

1. **Accounting-only hardening:** finish visible-session instrumentation and
   freeze a reproducible prose-packet baseline.
2. **Compression hardening:** add relevance fixes and compact fact packets, then
   compare against the frozen baseline.

Do not combine accounting changes with packet compression in one commit. A
clean measurement layer is the thing that lets the later compression result be
trusted.
