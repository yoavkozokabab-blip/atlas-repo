# Phase 94B — Impact Analysis Implementation

**Status:** Implemented  
**Date:** 2026-05-31  
**Design:** `reports/phase94b_impact_analysis_design.md` (followed exactly)

---

## Summary

Added a deterministic Impact Analysis Engine that consumes the Phase 94A dependency graph and answers the five builder questions (file/function/module dependents, execution paths, may-break scope) with separate **asserted**, **possible (unverified)**, and **unanalyzed** channels, plus independent **risk** and **confidence** scores.

No changes to detectors, benchmarks, promotion logic, `depgraph`, or `repository_understanding`.

---

## Deliverables

| Artifact | Path |
|----------|------|
| Engine | `builder_core/bug_intelligence/impact.py` |
| CLI | `builder_core.cli impact` (`--file`, `--module`, `--function`, `--paths-to`) |
| Feature flag | `IMPACT_ENABLED = True` (gates CLI registration) |
| Tests | `builder_core/tests/test_phase94b_impact_analysis.py` (11 tests) |
| Report | `reports/phase94b_impact_analysis_implementation.md` |

---

## Architecture

```
depgraph.build_graph(root)  ──read-only──►  impact.analyze_impact()
       │                                          │
       │ nodes, edges, unresolved, statistics     ├─ reverse indices (imports/calls/references)
       └──────────────────────────────────────────├─ direct impact (Q1–Q3)
                                                  ├─ transitive reverse BFS (Q5)
                                                  ├─ execution paths via entry files (Q4)
                                                  ├─ possible_additional_impact / unanalyzed
                                                  └─ risk + confidence (weights_version=1)
```

**Constants (reproducible):**

- `IMPACT_SCHEMA_VERSION = 1`, `WEIGHTS_VERSION = 1`
- `DEFAULT_MAX_DEPTH = 6`, `HARD_MAX_DEPTH = 25`, `MAX_IMPACT_SET_SIZE = 5000`
- Risk thresholds: low `< 0.35`, high `≥ 0.65`
- Confidence thresholds: high `≥ 0.85`, medium `≥ 0.50`, low `≥ 0.20`

---

## CLI

```powershell
py -3 -m builder_core.cli impact --project . --file actions/base.py
py -3 -m builder_core.cli impact --project . --module actions.base
py -3 -m builder_core.cli impact --project . --function actions/base.py::BaseAction.run
py -3 -m builder_core.cli impact --project . --paths-to actions/base.py::BaseAction.run
```

**Common options:** `--transitive`, `--direct`, `--max-depth`, `--top`, `--json [PATH]`

**Exit codes:** `0` = answered with high/medium confidence; `2` = degraded graph, unknown confidence, or target not found.

Optional JSON export: `<project>/.jarvis_builder/impact.json`

---

## local_jarvis verification

| Command | Result |
|---------|--------|
| `graph summary --project .` | OK — 9,493 nodes |
| `impact --file actions/base.py --top 5` | OK — 120 direct, 464 transitive dependents |
| Full test suite | **241 passed** |
| QuixBugs mini fixture | 1 TP / 0 FP (unchanged) |
| Holdout | `available: false` (unchanged) |

**Sample (`actions/base.py`):**

- Direct file dependents: 60+ production modules via `imports` + `references`
- Transitive closure: 464 nodes (not truncated)
- Execution paths: none resolved (expected — method dispatch not modeled)
- Risk: medium (0.62); confidence: medium (large unresolved call frontier repo-wide)

---

## Regression tests (design §13)

| # | Test | Covers |
|---|------|--------|
| 11 | `test_direct_and_transitive_function_impact` | A→B→C chain, evidence lines |
| 12 | `test_star_import_is_possible_not_asserted` | star_import in possible channel |
| 13 | `test_method_call_unresolved_verdict_unknown` | method call → unknown, exit 2 |
| 14 | `test_parse_error_listed_unanalyzed` | parse_errors → unanalyzed |
| 15 | `test_module_indegree_matches_statistics` | in-degree cross-check |
| 16 | `test_deterministic_json_bytes` | byte-identical JSON |

Additional: degraded graph, target-not-found, modules_importing, CLI smoke, benchmark unchanged.

---

## Rollback

Set `IMPACT_ENABLED = False` or delete `impact.py`, CLI block, and tests. No shared mutable state; no migrations.

---

## Commit

**Hash:** `d4fa1ff52fbb57bd03eac85cb9caa6c814225dcf`
