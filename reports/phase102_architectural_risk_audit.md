# Phase 102 Architectural Risk Audit

**Date:** 2026-06-01  
**Scope:** Phase 100G production-scoped dependency graph, Phase 101A
architectural-risk routing, committed Phase 102 v1 ranking, and proposed Phase
102 v2 plan.  
**Constraint:** Audit only. No production code changed.

## Verdict

**NO-GO** for treating the current Phase 102 output as a trusted architectural-risk
ranking, and **NO-GO** for implementing the proposed v2 plan unchanged.

Phase 101A routing works. Phase 100G prevents local corpus noise from degrading the
graph. The remaining blockers are trust problems in the ranking inputs, revision
freshness, portable scope filtering, graph metrics, and developer-facing evidence.

## What Works

| Check | Result | Evidence |
|---|---|---|
| Architectural-risk route | **PASS** | Exact query routes to `bottleneck`, `anchor:bottleneck`, not retrieval. See `builder_core/question_understanding.py:59-70`, `builder_core/ask.py:367-405`. |
| Local production scope | **PASS with portability caveats** | Live graph: 7,487 candidates, 674 kept, 6,813 excluded, not degraded. See `builder_core/bug_intelligence/depgraph.py:38-67`, `731-785`. |
| Local runtime modules | **PASS** | Eight `runtime/*.py` modules remain in production scope. Runtime is not excluded by the classifier. |
| Regression suite | **PASS** | `392 passed in 21.26s` for `builder_core/tests/`. |
| Deterministic v1 payload | **PASS** | Phase 102 tests pass and the response includes a structured breakdown. |

## Critical Issues

### C1. Test coverage and contract evidence are not trustworthy signals

`architectural_risk.rank_modules()` calls `risk._test_corpus()` and considers a
module tested when its basename stem is any substring of concatenated test paths
or test chunks (`builder_core/risk.py:23-32`,
`builder_core/architectural_risk.py:152`, `169`). This is a reference heuristic,
not coverage.

Read-only adversarial probe:

| Scenario for `payments.py` | `has_test_reference` | Untested penalty |
|---|---:|---:|
| No tests | `False` | `3.0` |
| Unrelated test prose contains `"payments"` | `True` | `0.0` |
| Test filename is `test_repayments.py` | `True` | `0.0` |
| Real test import | `True` | `0.0` |

The engine also names a score component `contract_evidence`, but
`_contract_evidence_score()` adds weight for every `python_analysis.findings`
entry, regardless of rule or whether it is contract-backed
(`builder_core/architectural_risk.py:114-127`). A probe with one arbitrary
`suspicious_conditional` finding produced `contract_evidence=2.0`.

The stored-index result shows the practical distortion:

- `builder_core.bug_intelligence.callgraph`: `contract_evidence=15.0`
- `builder_core.bug_intelligence.valueflow`: `contract_evidence=16.0`
- `runtime.task_lifecycle`: `contract_evidence=11.5`

These are static-finding weights labeled as contract evidence. They are not proof
of architectural risk.

The v2 plan acknowledges test presence as a stem match
(`reports/phase102_architectural_risk_ranking_plan.md:25-27`) and says a stronger
test import signal *may* be added (`:212`). That is insufficient. The engine must
not claim coverage or contract evidence until the underlying facts support those
names.

### C2. The answer can combine stale index facts with a live graph without warning

The CLI loads `.jarvis_builder/index.json` (`builder_core/cli.py:199-206`,
`builder_core/store.py:55-63`). The architectural query then rebuilds the graph
from the live tree (`builder_core/ask.py:148-154`) while Phase 102 consumes stale
index chunks, file metadata, churn, and `python_analysis`.

Observed during this audit:

| Item | Commit |
|---|---|
| Current `HEAD` | `d24f2dd02232d5cfdd7b0eb0cb38828ba7907d32` |
| Stored index commit | `b2871fafeeacbe247117ef4a8d68027580429a68` |

The response still reported `support_confidence="high"`. A developer cannot trust
a composite score built from mixed revisions unless staleness is surfaced and
index-derived enrichment is suppressed or explicitly marked stale.

### C3. Production scope is locally effective but unsafe as an arbitrary-repo rule

Phase 100G excludes top-level `data`, `dataset`, `datasets`, `fixtures`, and
`samples` trees (`builder_core/repository_understanding.py:55`,
`builder_core/bug_intelligence/depgraph.py:53-65`). It also excludes any nested
directory named `reports` as report history
(`builder_core/repository_understanding.py:114-115`).

Classifier probe:

| Path | Role / depgraph effect |
|---|---|
| `runtime/watchdog.py` | production, kept |
| `data/loader.py` | role says production, but depgraph drops top-level `data` |
| `fixtures/parser.py` | role says production, but depgraph drops top-level `fixtures` |
| `samples/client.py` | role says production, but depgraph drops top-level `samples` |
| `src/reports/service.py` | `report_history`, dropped |
| `generated/client.py` | generated, dropped |

For this repository, the local exclusion inventory is mostly correct: the large
`data/real_repo_corpus/` tree is evaluation data, and runtime modules are kept.
Outside corpora/backups/tests, the only locally excluded Python files were
`core/test_runtime.py` and `voice/streaming_stt/test_harness.py`, both plausibly
test-support code. That does not make the path rule safe for arbitrary repos.

### C4. Several structural metrics are gameable or dead

The v1 additive model does not reliably distinguish a large module from a
high-risk module (`builder_core/architectural_risk.py:18-31`, `186-197`).

Read-only probe:

| Module | Structure | Score |
|---|---|---:|
| `huge_leaf.py` | 2,500 LOC, zero fan-in, zero fan-out | `7.0` |
| `hub.py` | imported by another module | `4.0` |

The isolated leaf outranks the actual hub through capped LOC plus the default
untested penalty.

Fan-in is also counted per resolved import edge. Repeating `import hub` on three
lines produces three fan-in points because edge dedupe includes source line
(`builder_core/bug_intelligence/depgraph.py:580-592`).

The `component_root` bonus is effectively dead. `_largest_components()` unions
all graph edges, including repository containment edges
(`builder_core/bug_intelligence/depgraph.py:665-694`). The root becomes the
repository node, while Phase 102 compares component roots against module IDs
(`builder_core/architectural_risk.py:82-86`, `175`, `190`). The live top ranking
reported `component_root=0.0` for every module.

Cycle membership gets a reasonable additive signal, but cycle counts are
duplicated by rotation. `_import_cycles()` starts DFS from every adjacency key
without a global visited/canonical-SCC pass
(`builder_core/bug_intelligence/depgraph.py:697-728`). A single three-node cycle
was reported three times; a two-node cycle was reported twice.

## Medium Issues

### M1. The output is explainable at factor level, not evidentiary level

`format_ranking_evidence()` emits score dictionaries and a cycle count
(`builder_core/architectural_risk.py:284-294`). It does not cite:

- importer edges with file and line;
- canonical cycle paths;
- which test reference cleared the penalty;
- whether the reference was a filename, prose substring, or import;
- unresolved-edge counts and lower-bound warnings;
- index commit, live commit, or staleness;
- the fact source behind a claimed contract signal.

The live graph had 2,663 unresolved imports, 45,012 unresolved calls, and 538
unresolved references. The current response still labels support confidence high.

### M2. Structural centrality and architectural change risk are conflated

Phase 102 v1 calls its output an architectural-risk ranking even when fan-in
dominates. The proposed v2 plan correctly identifies this issue
(`reports/phase102_architectural_risk_ranking_plan.md:40-44`) and proposes a
`blast_radius * change_difficulty` core.

That is directionally better, but it can over-correct: a tiny, highly central
module may be easy to edit yet still deserve a prominent bottleneck warning. Keep
separate visible dimensions:

- structural bottleneck;
- change difficulty;
- safety-net quality;
- composite architectural change risk.

Do not erase centrality merely because a module is small.

### M3. Proposed v2 confidence is incomplete

The plan adds per-module confidence (`reports/phase102_architectural_risk_ranking_plan.md:189-193`),
which is valuable. Confidence must also account for:

- stale index versus live tree;
- heuristic-only test references;
- excluded-path ambiguity;
- duplicate import edges;
- unresolved dynamic or framework wiring;
- unavailable fact-backed contract evidence.

## False Positives And False Negatives

### Confirmed false-positive risks

| Risk | Cause |
|---|---|
| Large isolated leaf ranks above imported hub | LOC plus default untested weight |
| Repeated import statements inflate fan-in | Fan-in counts line-distinct edges |
| Generic static findings raise `contract_evidence` | Any finding severity is accepted |
| Package re-export modules rank as risky without context | High import fan-in may be expected architecture |

### Confirmed false-negative risks

| Risk | Cause |
|---|---|
| `data/loader.py` hidden | Top-level dataset-tree exclusion |
| `src/reports/service.py` hidden | Any nested `reports` directory becomes report history |
| Untested module treated as tested | Any stem substring in test prose or filename |
| Dynamic or framework-wired dependency omitted | Static graph unresolved edges are lower bounds |
| Tiny central module demoted too far in proposed v2 | Multiplicative difficulty gate can approach zero |

## Answers To Audit Questions

| Question | Answer |
|---|---|
| 1. Does the query route correctly? | **Yes.** Exact query reaches `bottleneck` through `anchor:bottleneck`. |
| 2. Does production scope hide important files? | **Locally mostly no; portably yes.** Runtime is kept, but ordinary source trees named `data`, `fixtures`, `samples`, or `reports` can be hidden. |
| 3. Are data/report/runtime/generated files excluded safely? | **No as a generic rule.** Local corpus exclusion is useful. Runtime is actually included. `reports` and top-level dataset-name exclusions need safer boundaries or explicit override. |
| 4. Can LOC game ranking? | **Yes.** A 2,500-LOC isolated leaf outranked a real hub. |
| 5. Are cycles and fan-in weighted correctly? | **No.** Fan-in is raw and repeatable by line; cycle count duplicates rotations; component-root score is dead. |
| 6. Are coverage signals real? | **No.** They are substring reference heuristics, not coverage. |
| 7. Large module versus high-risk module? | **Not reliably in v1.** v2 improves the model but needs dimension-preserving tests. |
| 8. False positives / negatives? | **Yes.** Confirmed with probes above. |
| 9. Enough evidence for developer trust? | **No.** Score breakdown exists, but source-grade evidence and freshness are missing. |

## Suggested Tests Before Phase 102 Continues

### P0 tests

1. `test_arch_risk_blocks_or_warns_on_stale_index_commit`
2. `test_unrelated_test_prose_does_not_clear_untested_signal`
3. `test_test_filename_substring_does_not_clear_untested_signal`
4. `test_real_test_import_is_reported_as_reference_not_coverage`
5. `test_generic_static_finding_does_not_count_as_contract_evidence`
6. `test_only_fact_backed_contract_signal_counts_as_contract_evidence`
7. `test_repeated_same_import_does_not_multiply_module_fan_in`
8. `test_one_cycle_has_one_canonical_cycle_id`
9. `test_component_root_metric_is_reachable_or_removed`
10. `test_top_level_data_loader_and_nested_reports_package_are_not_silently_hidden`

### P1 tests

1. `test_runtime_modules_remain_in_production_scope`
2. `test_known_corpus_tree_remains_excluded`
3. `test_large_isolated_leaf_does_not_rank_as_high_architectural_change_risk`
4. `test_small_high_fanin_module_remains_visible_as_structural_bottleneck`
5. `test_evidence_cites_importer_file_line_cycle_path_and_index_revision`
6. `test_unresolved_edges_lower_confidence`
7. `test_package_reexport_is_labeled_as_expected_coupling_candidate`

## Recommended Gate

### Phase 101A

**GO.** Routing is deterministic and regression-tested.

### Phase 100G

**GO for this repository's performance recovery.** It removes corpus noise and
restores a usable graph. Add portable scope-boundary tests before calling the
filter safe for arbitrary repositories.

### Phase 102 v1

**NO-GO for trusted developer output.** Keep it experimental only.

### Proposed Phase 102 v2

**NO-GO as currently written.** Amend the design before implementation:

1. replace coverage claims with typed test-reference evidence, or use real
   coverage only when measured;
2. consume fact-backed contract evidence only;
3. add freshness checks before mixing stored index facts with a live graph;
4. canonicalize fan-in and cycles, and repair or remove component-root scoring;
5. preserve centrality, difficulty, safety-net, and composite risk as separate
   visible dimensions;
6. emit source-grade evidence and lower confidence on unresolved or ambiguous
   scope.

## Commands Run

```text
py -3 -m pytest builder_core/tests/test_phase100g_depgraph_scope.py builder_core/tests/test_phase101a_architectural_risk_routing.py -q -p no:cacheprovider
12 passed in 2.49s

py -3 -m pytest builder_core/tests/test_phase102_architectural_risk_ranking.py -q -p no:cacheprovider
9 passed in 4.85s

py -3 -m pytest builder_core/tests/test_phase100g_depgraph_scope.py builder_core/tests/test_phase101a_architectural_risk_routing.py builder_core/tests/test_phase102_architectural_risk_ranking.py -q -p no:cacheprovider
21 passed in 2.06s

py -3 -m pytest builder_core/tests/ -q -p no:cacheprovider
392 passed in 21.26s
```

The first targeted pytest attempt inside the restricted sandbox failed before
test execution because pytest could not access its Windows temp root. The same
command passed when rerun with temp-directory access. Additional read-only Python
probes produced the false-positive and false-negative evidence recorded above.

## Files Changed By This Audit

```text
reports/phase102_architectural_risk_audit.md
```

