# Phase 100G — Dependency Graph Production-Scope Filter

**Status:** Implemented and verified.
**Date:** 2026-06-01
**Goal:** Stop the dependency graph from degrading on large repositories by
applying the existing RU-2 production-role filter before graph construction, so
generated/runtime/data/benchmark/report/test files do not push it over the cap.

---

## 1. Problem

Phase 101A fixed routing — the architectural-risk query now reaches the bottleneck
handler — but on the full `local_jarvis` repo the handler still returned
*"Dependency graph degraded — cannot compute architectural bottlenecks."*

`depgraph.build_graph` walked **every** `.py` via `engine._collect_python_files`
(which excludes only VCS/build dirs). The repo has **7,484 candidate `.py`**, of
which **~6,800 are non-production**, dominated by **`data/real_repo_corpus/`** (the
Phase 98A 24-repo evaluation corpus). That count exceeds `_MAX_FILES = 5000`, so
`build_graph_from_files` returned a **degraded (empty)** graph.

A subtle trap: the corpus `.py` under `data/real_repo_corpus/` classify as
`production_code` **by role** (the directory isn't benchmark-named, and `.py`
doesn't get the dataset role). So a role-only filter still kept ~3,808 files. The
fix also needs a **top-level data-tree exclusion**.

---

## 2. Fix

### 2.1 Entrypoint
The architectural handler chain is `ask._answer_bottlenecks → ask._build_depgraph →
depgraph.build_graph(root)`. The fix lives in `depgraph.build_graph` (also used by
`dependency_centrality`, `subsystem_centrality`, `impact`, and the `graph` CLI).

### 2.2 Production scope (reuses RU-2)
`build_graph(root, *, scope="production", include_tests=False)` — `production` is
the new default. It collects candidate paths, then keeps a file only when **both**:
- `repository_understanding.classify_file_role(...) == "production_code"`
  (or `"test"` when `include_tests=True`), **and**
- its top-level segment is not in RU-2's `_DATASET_PARTS`
  (`data`, `dataset`, `datasets`, `fixtures`, `samples`).

This reuses the existing RU-2 classifier and constant set — no new role logic. Role
handles generated/benchmark/report/test wherever nested; the data-tree check
catches first-party-looking corpora vendored under `data/`. Files are **read only
after filtering**, so the excluded I/O is also skipped.

`scope="full"` preserves the legacy every-file behavior. `include_tests=True` keeps
test files (intentional fixtures) on request.

### 2.3 `graph_scope` + diagnostics (result fields)
Every graph now carries:
```
graph_scope            production | full | degraded
scope_diagnostics:
  requested_scope        production | full
  include_tests          bool
  total_candidate_files  before filtering
  files_kept             after RU-2 filtering
  files_excluded
  excluded_by_role       {role|"dataset_tree": count, ...}
  degraded               bool
  cap_files / cap_functions
```
The bottleneck handler surfaces `graph_scope` and `scope_diagnostics` in its
`interpretation`.

---

## 3. Measured result (real repo)

`depgraph.build_graph('.')` (production default):

| Metric | Value |
|---|---:|
| `graph_scope` | **production** |
| total candidate files | 7,484 |
| **files kept** | **673** |
| files excluded | 6,811 |
| excluded — `dataset_tree` | 3,143 |
| excluded — `test` | 2,934 |
| excluded — `generated` | 698 |
| excluded — `benchmark` | 29 |
| excluded — `report_history` | 7 |
| degraded | **False** |
| nodes / edges | 6,523 / 14,456 |

Top import fan-in: **`config` ← 212**, `core.logger` ← 144, `core.types` ← 133,
`core.results` ← 65, `actions.base` ← 60, `actions.registry` ← 23; **4 import
cycles**.

### Exact failing query, end-to-end
```
"Rank the top architectural risk modules in this repository using dependency
 graph fan-in, module size, import cycles, and test coverage."

mode: bottleneck   |  retrieval-fallback: False  |  degraded: False
Critical architectural bottlenecks (import fan-in, cycles, component roots):
  1. config: score=212 (import fan-in=212)
  2. core.logger: score=144 ...
  3. core.types: score=133 ...
  ...
```
It now returns an **actual architectural-risk ranking**, not retrieval and not
degraded mode — the Phase 100G expected result.

---

## 4. Tests

`builder_core/tests/test_phase100g_depgraph_scope.py` (6), on a synthetic repo
whose non-production files outnumber its source (production hub + cycle, plus
`data/corpus/*.py`, `generated/`, `reports/`, `tests/`):

| Test | Proves |
|---|---|
| `…excludes_noise_and_does_not_degrade` | with a tiny cap, `full` degrades but `production` does not |
| `…scope_diagnostics_report_filtering` | diagnostics report candidates/kept/excluded incl. `dataset_tree`, `generated`, `report_history`, `test` |
| `…production_files_kept_and_noise_excluded` | `core/util.py` kept; no `data/`, `generated/`, `reports/`, `tests/` nodes |
| `…include_tests_keeps_tests` | `include_tests=True` keeps tests but still drops `data/` |
| `…full_scope_keeps_everything` | legacy `full` scope keeps `data/` modules |
| `…bottleneck_query_returns_ranking_despite_data_noise` | the architectural-risk query → `bottleneck` mode, real fan-in ranking, `graph_scope=production`, not retrieval/degraded |

---

## 5. Verification

```
py -3 -m pytest builder_core/tests/test_phase100g_depgraph_scope.py -q
6 passed

py -3 -m pytest builder_core/tests/ -q
383 passed

py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
12 true positives, 0 false positives, precision 1.0000
```

End-to-end exact failing query: returns the ranking above (mode `bottleneck`).

---

## 6. Files & safety

```
Modified:
  builder_core/bug_intelligence/depgraph.py   # production scope + graph_scope + diagnostics
  builder_core/ask.py                          # surface graph_scope in bottleneck interpretation
Added:
  builder_core/tests/test_phase100g_depgraph_scope.py
  reports/phase100g_depgraph_scope_filter.md
```

- Reuses the RU-2 classifier + `_DATASET_PARTS`; **no new role logic**, no detector,
  finding, benchmark, or promotion change (full suite 383; QuixBugs 12/0).
- `build_graph_from_files`, the graph schema, and all downstream consumers are
  unchanged; only the file set fed in and two additive result fields differ.
- Deterministic and honest: if a production graph still exceeds the cap it reports
  `graph_scope="degraded"` rather than guessing.
- Companion to `reports/phase100g_break_even_optimization.md`, which identified this
  scope bloat as the primary build-cost and degradation driver.
