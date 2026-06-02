# Phase 104C Compact Fact Packets Audit

**Date:** 2026-06-01  
**Verdict:** **NO-GO**  
**Scope:** Read-only audit of compact context generation. No production code modified.

## 1. Executive Summary

Phase 104C meets the aggregate token-reduction target but does not yet preserve
enough evidence, uncertainty, or task specificity to use compact packets as the
default context for Codex or Claude.

Measured against the frozen 21-task Phase 103 benchmark corpus:

| Metric | Result |
|---|---:|
| Current prose packets | `9,886` estimated tokens |
| Current compact packets | `4,688` estimated tokens |
| Aggregate reduction | `52.58%` |
| Target | `>=50%` and `<5,000` compact tokens |
| Size verdict | **PASS** |
| Trust verdict | **FAIL** |

The size win is real. The trust blockers are also real:

1. Six truncated packets exceed their declared hard caps after truncation
   metadata is appended.
2. All three architectural-risk packets lose every source reference.
3. Contract packets collapse to source paths without contract facts.
4. Fixture defect packets omit the actual defect evidence and do not cite the
   fixed fixture.
5. Short required-evidence names resolve to non-existent graph targets for
   `impact03_contract_facts` and `plan02_verification`.
6. Several semantically different tasks still receive effectively the same
   context shape.
7. Prose mode stays text-compatible but now performs compact comparison work
   eagerly, adding analysis cost and failure surface even when compact mode is
   off.

Compact mode should remain opt-in until these blockers are fixed.

## 2. Repository State

The repository changed during this audit:

```text
13397ee9 Phase 104B: profile benchmark JARVIS context generation time and tokens
d9c77e23 Phase 104C: compact fact packets for benchmark JARVIS context
daa204d9 Phase 104D: cache expensive benchmark context stages for speed
```

The initial measurement was run against the Phase 104C serializer while Phase
104C and Phase 104D landed concurrently. A diff of `d9c77e23..daa204d9` confirms
that Phase 104D adds optional session/cache plumbing but leaves the no-cache
packet construction and truncation behavior unchanged.

This audit therefore describes the current `HEAD` behavior with compact cache
disabled, which is the default.

## 3. Audit Method

The audit used:

```text
builder_core/benchmark_framework/data/benchmark_tasks_v1.json
```

For each of the 21 frozen tasks:

1. Build the current Builder index.
2. Run `ask.answer(index, task.prompt)`.
3. Render the existing prose context with `format_jarvis_packet()`.
4. Render compact context with `build_compact_packet()`.
5. Count tokens with the existing `ceil(chars / 4)` estimator.
6. Check caps, truncation markers, source references, caveats, and exact
   duplicate packet strings.
7. Inspect high-risk packet families manually.

The current prose total differs slightly from the earlier Phase 104C design
baseline (`9,963`) because the repository state changed while implementation
landed. The implementation audit uses the freshly rendered current total
(`9,886`).

## 4. Token Reduction

### 4.1 Aggregate

| Metric | Value |
|---|---:|
| Prose packet total | `9,886` |
| Compact packet total | `4,688` |
| Tokens removed | `5,198` |
| Reduction | `52.58%` |
| Compact average per task | `223.24` |
| Required compact total | `<5,000` |
| Required reduction | `>=50%` |

**Result:** PASS.

### 4.2 Per-task measurements

| Task | Kind | Prose | Compact | Reduction |
|---|---|---:|---:|---:|
| `ru01_subsystems` | `REPO_MAP` | `610` | `378` | `38.0%` |
| `ru02_builder_core_map` | `REPO_MAP` | `475` | `377` | `20.6%` |
| `ru03_voice_path` | `REPO_MAP` | `578` | `377` | `34.8%` |
| `dep01_engine_edges` | `DEPENDENCY` | `329` | `225` | `31.6%` |
| `dep02_ask_edges` | `DEPENDENCY` | `493` | `240` | `51.3%` |
| `dep03_evidence_chain` | `DEPENDENCY` | `339` | `88` | `74.0%` |
| `impact01_config` | `IMPACT` | `804` | `203` | `74.8%` |
| `impact02_engine` | `IMPACT` | `109` | `123` | `-12.8%` |
| `impact03_contract_facts` | `IMPACT` | `401` | `44` | `89.0%` |
| `risk01_ranking` | `ARCH_RISK` | `804` | `425` | `47.1%` |
| `risk02_centrality_vs_risk` | `ARCH_RISK` | `804` | `425` | `47.1%` |
| `risk03_cycles` | `ARCH_RISK` | `401` | `424` | `-5.7%` |
| `contract01_sources` | `CONTRACT` | `312` | `62` | `80.1%` |
| `contract02_inconsistent_return` | `CONTRACT` | `331` | `49` | `85.2%` |
| `verify01_evidence_types` | `VERIFY` | `701` | `326` | `53.5%` |
| `verify02_non_promotion` | `VERIFY` | `263` | `263` | `0.0%` |
| `defect01_wrong_operator` | `DEFECT_REVIEW` | `525` | `91` | `82.7%` |
| `defect02_bfs_queue` | `DEFECT_REVIEW` | `582` | `101` | `82.6%` |
| `defect03_gate` | `DEFECT_REVIEW` | `327` | `64` | `80.4%` |
| `plan01_config` | `PLAN_INPUT` | `401` | `248` | `38.2%` |
| `plan02_verification` | `PLAN_INPUT` | `297` | `155` | `47.8%` |

The aggregate passes, but several large reductions come from removing required
facts rather than encoding them more efficiently.

## 5. Evidence Preservation

### 5.1 Architectural-risk references are dropped

The truncation implementation removes rows from the tail until the body fits,
then appends `TRUNCATED` and `DETAIL` rows without rechecking the final size.
References and graph rows are at the tail.

Affected packets:

| Task | Hard cap | Actual compact tokens | References after truncation |
|---|---:|---:|---:|
| `risk01_ranking` | `400` | `425` | `0` |
| `risk02_centrality_vs_risk` | `400` | `425` | `0` |
| `risk03_cycles` | `400` | `424` | `0` |

The packets retain ranked module rows but lose source references and graph
summary evidence.

### 5.2 Contract facts are absent

`contract01_sources` renders only:

```text
PACKET|V=1|KIND=CONTRACT|MODE=retrieval|SCOPE=production
REF|ID=R1|PATH=builder_core/scripts/phase96d_review_pilot.py
REF|ID=R2|PATH=builder_core/bug_intelligence/contract_facts.py
REF|ID=R3|PATH=builder_core/bug_intelligence/contract_enrichment.py
```

`contract02_inconsistent_return` renders only:

```text
PACKET|V=1|KIND=CONTRACT|MODE=retrieval|SCOPE=production
REF|ID=R1|PATH=builder_core/bug_intelligence/confirmed_defect_gate.py
REF|ID=R2|PATH=builder_core/bug_intelligence/contract_enrichment.py
```

Neither packet preserves contract-source kinds, strength limits, quarantine
reasoning, or proof obligations. The serializer only emits contract rows for a
matching Python analysis containing `wrong_return_shape`, which does not fit
these repository-level questions.

### 5.3 Defect packets omit the defect

`defect01_wrong_operator` renders:

```text
TARGET|PATH=classic_wrong_operator/buggy.py
CAVEAT|CODE=REVIEW_LEAD_NOT_CONFIRMED|VALUE=yes
```

plus references. It does not cite `fixed.py`, identify the changed operator, or
explain the behavioral consequence.

`defect02_bfs_queue` has the same problem: it does not cite the fixed fixture,
state the empty-queue failure, or encode the BFS invariant.

These packets cannot support the required confirmed-defect tasks.

### 5.4 Impact targets can resolve incorrectly

`_target_from_task()` selects the first required-evidence item ending in `.py`
before resolving it against indexed repository paths.

Observed results:

```text
impact03_contract_facts
TARGET|PATH=contract_facts.py
IMPACT|DIRECT=0|TRANSITIVE=0|RISK=unknown|CONFIDENCE=unknown

plan02_verification
TARGET|PATH=verification_evidence.py
IMPACT|DIRECT=0|TRANSITIVE=0|RISK=unknown|CONFIDENCE=unknown
```

The real paths are:

```text
builder_core/bug_intelligence/contract_facts.py
builder_core/bug_intelligence/verification_evidence.py
```

The compact packets are small because the graph lookup misses the real module.

### 5.5 Verification retrieval leaks irrelevant corpus evidence

`verify01_evidence_types` includes:

```text
data/real_repo_corpus/phase98a/attrs/docs/types.md
```

The compact serializer preserves a retrieval leak instead of selecting the
verification-evidence implementation as the focused proof source.

**Evidence-preservation result:** FAIL.

## 6. Uncertainty Preservation

Some safeguards survive:

- verification packets retain `CAVEAT|CODE=NON_PROMOTING_EVIDENCE`;
- defect packets retain `CAVEAT|CODE=REVIEW_LEAD_NOT_CONFIRMED`;
- impact packets retain explicit `RISK=unknown|CONFIDENCE=unknown` when graph
  targets miss.

Important uncertainty is still lost:

1. Contract packets omit `USAGE_CONTRACT_NOT_PROVEN` when no matching Python
   analysis is found.
2. Tail truncation can remove caveat rows and graph degradation evidence.
3. Risk packets lose the graph summary that tells the reader whether ranking
   evidence is degraded.
4. Empty impact packets expose `unknown` but do not explain that target
   resolution failed.

**Uncertainty-preservation result:** FAIL.

## 7. Duplicate and Generic Context

The audit found no byte-identical compact packet strings across the 21 tasks.
That is not sufficient to pass task specificity.

Several packet groups remain semantically duplicated:

| Tasks | Problem |
|---|---|
| `risk01_ranking`, `risk02_centrality_vs_risk`, `risk03_cycles` | All receive the same global top-12 module ranking shape. The cycles question does not receive canonical cycle evidence. |
| `ru01_subsystems`, `ru02_builder_core_map`, `ru03_voice_path` | All receive the same top subsystem inventory shape. The voice-path question does not receive a microphone-to-router-to-action-to-overlay/TTS path. |

Minor differences such as `SRCQ`, mode, or `DETAIL` digest prevent byte equality
without making the packet answer the requested question.

**Task-specificity result:** FAIL.

## 8. Answer Quality Sufficiency

Compact mode preserves useful facts for a subset of questions:

- `impact01_config` has a useful target, counts, representative dependents,
  caveat, and references.
- dependency packets preserve edge rows and references when targets resolve.
- risk packets preserve ranked metrics even though references are lost.

It does not preserve enough facts for the full benchmark corpus:

| Family | Sufficiency |
|---|---|
| Repository understanding | Partial. Subsystem inventory exists, but voice execution path and Builder Core surface map are not specialized. |
| Dependency analysis | Partial. Named full-path targets work better than abbreviated module targets. |
| Impact analysis | Partial. Full paths can work; abbreviated paths silently miss. |
| Architectural risk | Partial. Metrics remain, but references and cycle-specific evidence are lost. |
| Contract analysis | Fail. Facts and proof limits are missing. |
| Verification evidence | Partial. Generic retrieval facts remain, including irrelevant corpus material. |
| Confirmed defect detection | Fail. Actual fixture diffs and behavioral evidence are missing. |
| Fix planning | Partial. `config.py` is useful; abbreviated verification target silently misses. |

A manual Codex/Claude answer-quality run was not performed in this audit.
Static packet inspection is already sufficient to fail the quality gate:
required evidence is absent before any model sees the prompt.

**Answer-quality sufficiency result:** FAIL.

## 9. Benchmark Scoring and Analysis Behavior

### 9.1 Scoring

No Phase 104C diff was found in:

```text
builder_core/benchmark_framework/scoring.py
builder_core/benchmark_framework/summary.py
builder_core/benchmark_framework/schema.py
builder_core/ask.py
builder_core/architectural_risk.py
builder_core/repository_understanding.py
```

The manual score template and summary aggregation remain unchanged.

**Benchmark-scoring change result:** PASS.

### 9.2 Default production behavior

With no environment override:

```text
DEFAULT_FORMAT=prose
DEFAULT_MATCHES_PROSE=True
SELECTED=prose
```

Compact mode is opt-in through:

```text
JARVIS_CONTEXT_PACKET_FORMAT=compact
```

**Default output compatibility result:** PASS.

### 9.3 Accidental eager analysis work

`format_jarvis_context()` always calls `compare_context_formats()`.
`compare_context_formats()` always builds the compact packet. For impact,
dependency, and risk families, compact packet construction can build graph,
impact, and ranking data even when the selected output format is `prose`.

Phase 104D adds optional caching but does not remove the eager comparison.

This does not alter manual scoring semantics, but it changes runtime cost and
adds a new failure surface in the prose path.

**Analysis-behavior change result:** FAIL.

## 10. Cap Enforcement

Six packets exceed their own hard caps:

| Task | Kind | Cap | Actual |
|---|---|---:|---:|
| `ru01_subsystems` | `REPO_MAP` | `350` | `378` |
| `ru02_builder_core_map` | `REPO_MAP` | `350` | `377` |
| `ru03_voice_path` | `REPO_MAP` | `350` | `377` |
| `risk01_ranking` | `ARCH_RISK` | `400` | `425` |
| `risk02_centrality_vs_risk` | `ARCH_RISK` | `400` | `425` |
| `risk03_cycles` | `ARCH_RISK` | `400` | `424` |

Root cause:

```text
builder_core/benchmark_framework/compact_packets.py
_apply_cap()
```

The function trims rows until the pre-metadata body fits, then appends
`TRUNCATED` and `DETAIL` rows. It does not reserve metadata space or recheck the
final token count.

**Cap-enforcement result:** FAIL.

## 11. Tests

### 11.1 Commands run

```powershell
py -3 -m pytest builder_core/tests/test_phase103_benchmark_framework.py builder_core/tests/test_phase104a_token_accounting.py builder_core/tests/test_phase104b_context_profiling.py -q -p no:cacheprovider
```

Result:

```text
12 passed, 7 setup errors
```

All errors are environmental:

```text
PermissionError: [WinError 5] Access is denied:
C:\Users\babi2\AppData\Local\Temp\pytest-of-babi2
```

The workspace-local `--basetemp` retry was also denied by the sandbox. Two
outside-sandbox retry requests timed out during approval review before pytest
ran.

```powershell
py -3 -m pytest builder_core/tests/test_phase104c_compact_fact_packets.py -q -p no:cacheprovider
```

Result:

```text
6 setup errors
```

The same temp-root permission error occurred before Phase 104C assertions ran.

### 11.2 Test coverage gaps

The tracked Phase 104C tests do not cover the production-corpus failures:

- no frozen 21-task aggregate `<5,000` assertion;
- no real-packet hard-cap assertion;
- no reference-preservation assertion after truncation;
- no contract-fact preservation assertion;
- no fixture diff and fixed-file reference assertion;
- no abbreviated-target normalization assertion;
- no semantic duplicate detection;
- no corpus-source exclusion assertion;
- no proof that prose mode avoids extra compact analysis work.

The current uncertainty test is insufficient because it accepts:

```text
assert "CAVEAT|" in compact or "MODE=" in compact
```

Every packet header has a mode, so the test can pass without preserving any
uncertainty.

## 12. Required Fixes

1. Fix `_apply_cap()` to reserve space for mandatory metadata and preserve
   mandatory `CAVEAT`, `REF`, graph-state, and scope rows before optional facts.
2. Recheck the final serialized token count after `TRUNCATED` and `DETAIL` rows
   are added.
3. Normalize abbreviated `.py` evidence names to one unambiguous indexed path;
   emit a target-resolution caveat when zero or multiple matches exist.
4. Build contract packets from contract infrastructure facts for repository
   questions, not only matching file analyses with `wrong_return_shape`.
5. Build fixture defect packets from both buggy and fixed files and encode the
   behavioral difference.
6. Add specialized packets for cycle interpretation, Builder Core surface
   mapping, and voice execution-path questions.
7. Exclude real-repository corpus paths from verification retrieval context.
8. Avoid compact comparison work on the default prose path unless explicitly
   profiling or generating comparison artifacts.
9. Add frozen-corpus preservation and cap tests before promoting compact mode.

## 13. Final Verdict

**NO-GO**

Phase 104C proves that a `>=50%` packet-size reduction is achievable. It does
not yet prove safe information-preserving compression.

Keep:

```text
JARVIS_CONTEXT_PACKET_FORMAT=prose
```

as the default until the evidence, uncertainty, targeting, and cap-enforcement
blockers are fixed and the frozen 21-task corpus passes preservation tests.
