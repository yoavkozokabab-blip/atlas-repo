# Phase 102B Architectural Risk Trust Audit

**Date:** 2026-06-01  
**Audited commit:** `82f8b5f0` (`Phase 102B: harden architectural risk ranking trust and diagnostics`)  
**Scope:** Read-only trust audit of Phase 102B only. No production code changed.

## Verdict

**NO-GO** for presenting Phase 102B as a trusted architectural-risk engine.

Phase 102B makes real progress: fake test prose no longer marks modules tested,
repeated imports no longer inflate fan-in, ranking-level cycles are canonical,
dead `component_root` scoring is removed, and score diagnostics are materially
better.

Four trust blockers remain:

1. an untested isolated large file can still collect the full LOC score and
   outrank a real hub;
2. `contract_evidence` still scores contract-shaped findings before any extracted
   contract fact is required;
3. production scope still hides legitimate source folders in arbitrary repos;
4. the output still presents one blended architectural-risk total instead of
   separating structural centrality from change risk.

An additional trust blocker remains from Phase 102: stale index facts can be
combined with a live graph while support confidence stays `high`.

## Gate Results

| # | Trust gate | Result |
|---:|---|---|
| 1 | Can fake test prose still mark a module as tested? | **PASS** |
| 2 | Can repeated imports inflate fan-in? | **PASS** |
| 3 | Are cycles canonical and non-duplicated? | **PASS for Phase 102 output** |
| 4 | Can LOC alone dominate ranking? | **FAIL** |
| 5 | Are contract signals backed by real contract facts? | **FAIL** |
| 6 | Does production scope exclude legitimate source folders? | **FAIL** |
| 7 | Does output distinguish risk from centrality? | **FAIL / partial improvement only** |

## Critical Issues

### C1. LOC still inverts rankings for untested isolated files

Phase 102B gates LOC through `_blast_radius_or_safety_gap()`, but one gate is
`or not has_test_reference` (`builder_core/architectural_risk.py:449-467`).
Therefore, every untested isolated large file remains LOC-eligible even when it
has zero fan-in, zero fan-out, no cycle, no subsystem-hub signal, and no static
or contract evidence.

Read-only in-memory probe:

| Module | Structure | Total | LOC component |
|---|---|---:|---:|
| `huge_leaf.py` | 2,500 LOC, isolated, untested | `7.0` | `4.0` |
| `hub.py` | imported by another module, untested | `4.0` | `0.0` |

The only score difference that causes the inversion is LOC.

The bundled regression does not cover this case. It gives the isolated large
file a real test import (`builder_core/tests/test_phase102b_architectural_risk_trust.py:93-113`),
which suppresses both the untested signal and LOC eligibility.

### C2. Contract evidence does not require a real contract fact

`_contract_evidence_score()` immediately scores any finding whose rule is in
`CONTRACT_FINDING_RULES`, then *optionally* extracts contract facts when source
text is available (`builder_core/architectural_risk.py:337-411`).

Read-only probe:

```text
analysis finding only:
  inconsistent_return (high)
  source text: unavailable
  extracted contract facts: none
  contract_evidence score: 1.5

same finding with extractable type-hint facts:
  contract_evidence score: 4.0 capped
  evidence count: 6
```

Phase 102B correctly separates unrelated static findings into
`static_findings`, but its contract channel still mixes:

- a contract-shaped review lead;
- extracted contract obligations;
- no requirement that an obligation is actually violated.

This is better labeling than Phase 102 v1, but it is not fact-backed contract-risk
evidence.

### C3. Production scope still hides legitimate source folders

Phase 102B does not change Phase 100G scope filtering. The default production graph
excludes top-level dataset-name trees and any nested `reports` directory:

- `_DATASET_PARTS = {"data", "dataset", "datasets", "fixtures", "samples"}`
  (`builder_core/repository_understanding.py:55`);
- nested `reports` becomes `report_history`
  (`builder_core/repository_understanding.py:114-115`);
- top-level dataset-name trees are removed from depgraph production scope
  (`builder_core/bug_intelligence/depgraph.py:53-65`).

Read-only classifier/filter probe:

| Path | Result |
|---|---|
| `runtime/watchdog.py` | kept |
| `data/loader.py` | excluded as `dataset_tree` |
| `fixtures/parser.py` | excluded as `dataset_tree` |
| `samples/client.py` | excluded as `dataset_tree` |
| `reports/service.py` | excluded as `report_history` |
| `src/reports/service.py` | excluded as `report_history` |
| `generated/client.py` | excluded as generated |

The local JARVIS corpus exclusion remains useful, and runtime source is kept.
The generic rule is still unsafe for arbitrary repositories.

### C4. Risk and centrality remain blended

Phase 102B adds better `score_breakdown` and `rank_diagnostics`, but the answer
still emits one `total_score`, sorted descending, under the heading
`Architectural risk ranking` (`builder_core/architectural_risk.py:654`,
`684-695`).

There is no separate:

- `centrality_score`;
- change-risk score;
- safety-net score;
- risk band;
- explicit "central but low change-risk" classification.

Live exact-query result:

| Module | Total | Fan-in contribution | Test evidence |
|---|---:|---:|---:|
| `config` | `212.8` | `206.0` | `-1.5` |
| `core.logger` | `145.0` | `144.0` | `-1.5` |
| `core.types` | `134.86` | `133.0` | `-1.5` |

`core.logger` remains ranked almost entirely because it is central. That may be
useful structural evidence, but the result calls it architectural risk without
distinguishing centrality from difficulty or fragility.

## Additional Trust Issue

### A1. Stale index facts still mix with a live graph without warning

The exact query rebuilds a live depgraph through `ask._build_depgraph()`
(`builder_core/ask.py:148-154`) while consuming cached index metadata and
analysis. During this audit:

| Item | Commit |
|---|---|
| Live `HEAD` | `82f8b5f0dbbbbdf2ddcdcca7b06b8d67edfe831f` |
| Cached `.jarvis_builder/index.json` | `b2871fafeeacbe247117ef4a8d68027580429a68` |

The response still returned `support_confidence="high"`. Phase 102B does not
surface revision freshness or suppress stale enrichments.

## Passed Gates

### P1. Fake test prose is blocked

Phase 102B builds test evidence from AST import candidates before resolving
references (`builder_core/architectural_risk.py:271-322`).

Read-only in-memory probe for `payments.py`:

| Test content | Marked tested? |
|---|---:|
| No test | No |
| Plain prose containing `payments` | No |
| Docstring containing `payments.charge` | No |
| Comment containing `payments.charge` | No |
| Undefined `payments.charge()` call without import | No |
| Real `from payments import charge` test | Yes |

This is a test-reference signal, not measured coverage. Phase 102B should keep
calling it a reference or binding.

### P2. Repeated imports no longer inflate fan-in

`_dedupe_import_edges()` counts unique `(importer, imported)` pairs
(`builder_core/architectural_risk.py:96-118`).

Probe:

```text
import hub
import hub
from hub import helper

deduped import pairs: 1
hub fan-in: 1
```

### P3. Ranking-level cycles are canonical

`_canonical_import_cycles()` canonicalizes rotations and deduplicates them
(`builder_core/architectural_risk.py:121-133`).

Probe:

```text
raw depgraph rotations: 3
Phase 102B canonical cycles: 1
```

The underlying depgraph statistics still contain rotated duplicates. Phase 102B
output is correct; shared depgraph consumers should not assume raw cycles are
canonical.

## Suggested Tests

### P0

1. `test_untested_isolated_large_file_does_not_collect_loc_score`
2. `test_untested_isolated_large_file_does_not_outrank_real_hub`
3. `test_contract_shaped_finding_without_bound_contract_fact_does_not_score_contract_evidence`
4. `test_contract_obligation_without_violation_is_not_risk_evidence`
5. `test_arch_risk_reports_centrality_and_change_risk_separately`
6. `test_arch_risk_warns_when_cached_index_commit_differs_from_live_head`
7. `test_arch_risk_downgrades_confidence_when_index_is_stale`
8. `test_source_packages_named_data_fixtures_samples_reports_are_not_silently_excluded`

### P1

1. `test_runtime_source_remains_in_production_scope`
2. `test_known_real_repo_corpus_remains_excluded`
3. `test_raw_depgraph_cycle_consumers_receive_canonical_cycles_or_explicit_raw_label`
4. `test_test_binding_is_labeled_reference_not_coverage`
5. `test_central_but_tiny_tested_module_is_visible_without_being_called_high_risk`

## Verification

```text
py -3 -m pytest builder_core/tests/test_phase102b_architectural_risk_trust.py builder_core/tests/test_phase102_architectural_risk_ranking.py builder_core/tests/test_phase100g_depgraph_scope.py builder_core/tests/test_phase101a_architectural_risk_routing.py -q -p no:cacheprovider
29 passed in 2.90s

py -3 -m pytest builder_core/tests/ -q -p no:cacheprovider
400 passed in 21.33s
```

Additional read-only in-memory probes verified:

- fake test prose rejection;
- AST test-import acceptance;
- unique-pair fan-in;
- canonical cycle output;
- LOC inversion;
- contract-shaped finding scoring without extracted facts;
- arbitrary-repository scope exclusions;
- live exact-query ranking and stale-index mismatch.

## Recommendation

**NO-GO** until the P0 blockers are fixed.

Keep Phase 102B as a useful experimental structural ranking, but do not present
its blended total as a trusted architectural-risk score. The shortest safe next
step is to preserve centrality as its own visible dimension, restrict LOC to
actual dependency or evidence-bearing contexts, require bound contract facts for
the contract channel, add revision freshness handling, and make production scope
overridable or source-root-aware.

## Files Changed By This Audit

```text
reports/phase102b_architectural_risk_trust_audit.md
```
