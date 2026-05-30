# Phase 87 — Dataflow-Backed Rule Rewire

**Status:** Implemented and verified
**Date:** 2026-05-30
**Scope:** Replace name-bound BFS/visited semantic rules with one behavior-bound,
dataflow-backed finding. No new bug categories; recall not chased.

---

## 0. TL;DR

- Added **one** dataflow-backed finding, `unguarded_container_consumption`,
  derived purely from Phase 86 data-flow facts — **no function name, variable
  name, file name, or path** is used to decide a hit.
- **Retired** three name/shape-bound rules: `bfs_frontier_termination`,
  `bfs_missing_visited_tracking`, `graph_traversal_cycle_handling`, and the
  **BFS branch inside `algorithm_mismatch`**.
- **Holdout precision improved 66.7% → 100%** (corrected-BFS false positive
  eliminated); holdout recall held at 16.7%; QuixBugs recall held at 30%
  (≥ 25%), QuixBugs precision stayed 100%.

---

## 1. Rules retired

| Retired rule | Where | Why retired |
|---|---|---|
| `bfs_frontier_termination` | `semantic_reasoning._bfs_findings` | Name/shape-bound (required a `queue`-named var + `bfs` profile). Its job — detecting a frontier loop that doesn't terminate on emptiness — is now done name-free by the dataflow rule. |
| `bfs_missing_visited_tracking` | `semantic_reasoning._bfs_findings` | Encoded a **false universal** ("every traversal must have a visited set"). Source of the Phase 84 holdout false positive on correct, acyclic traversals. |
| `graph_traversal_cycle_handling` | `semantic_reasoning._generic_profile_findings` | Same false universal as above for the `dfs`/`graph_traversal` profiles; out-of-domain false positives. |
| BFS branch of `algorithm_mismatch` | `bug_intelligence/patterns.detect_algorithm_mismatch` | Hard-coded on `"breadth_first"`/`"bfs"` names and `"queue"`/`"successor"` variable words. The queue-as-stack and missing-visited heuristics were name-matched and non-transferable. |

Kept (still name-bound, **out of Phase 87 scope** — see §5): `bfs_queue_exhaustion`,
`bfs_fifo_violation`, `bfs_cycle_handling`, the recursion/shortest-path/sorting
named checks, and the DFS/binary-search/factorial/fibonacci/gcd branches of
`algorithm_mismatch`.

---

## 2. New dataflow-backed rule: `unguarded_container_consumption`

**Detection (100% structural, name-free).** Built on the Phase 86 fact layer
(`builder_core/bug_intelligence/dataflow.py`). It fires when a **`while`** loop:

1. **consumes** a container every iteration (`pop`/`popleft`/`remove`/…), **and**
2. its **guard does not depend on that container**
   (`termination_depends_on_consumed_container == False`), **and**
3. there is **no empty-container exit before the consumption**
   (`has_empty_guard_before_consume == False`), **and**
4. the same container is **also grown** in the loop (self-expanding worklist:
   `consumes ∩ grows ≠ ∅`).

It is restricted to `while` loops on purpose: a `for` loop always terminates by
exhausting its finite iterator, so popping an auxiliary stack inside a `for`
loop (RPN evaluation, shunting-yard) is **not** a non-termination bug. Lifting
this restriction produced two QuixBugs false positives during development
(`rpn_eval.py`, `shunting_yard.py`); the `while`-only rule removes them.

**It never reads** the function name, variable names, the file name, or any
QuixBugs path. Proof: it flags a buggy BFS even after the function is renamed to
`f1` and every variable to `v0/v1/…` (see `test_renamed_buggy_bfs_still_flags`),
and it does not flag the corrected version under the same renaming.

**Wiring:**
- Semantic path (drives the benchmarks): `semantic_reasoning.analyze_semantics`
  calls `dataflow.find_unbounded_frontier_loops` once per module and emits the
  finding with `kind="semantic"`.
- Pattern path (CLI `analyze-file` / `bug-scan`): new detector
  `patterns.detect_unguarded_container_consumption`, registered in
  `ALL_DETECTORS`.

Both paths share the single fact query `dataflow.find_unbounded_frontier_loops`,
so there is one source of truth.

---

## 3. Before / after benchmark

### QuixBugs (in-domain, buggy vs correct pairs)
| Metric | Before (Phase 83D baseline) | After (Phase 87) |
|---|---|---|
| Buggy files analyzed | 40 | 40 |
| True positives | 12 | 12 |
| False positives | 0 | 0 |
| Precision | 100% | **100%** |
| Recall | 30% | **30%** |

`breadth_first_search.py` is now flagged by **both** the kept `bfs_queue_exhaustion`
**and** the name-free `unguarded_container_consumption`. Recall is unchanged
(the new rule overlaps the existing BFS TP in-domain); its value is transfer, not
in-domain recall.

### External holdout (out-of-domain / transfer)
| Metric | Before (Phase 84) | After (Phase 87) |
|---|---|---|
| Cases analyzed | 12 | 12 |
| True positives | 2 | 2 |
| False positives | **1** | **0** |
| Precision | 66.7% | **100%** |
| Recall | 16.7% | **16.7%** |
| False positives on fixed code | 1 | **0** |

### Acceptance criteria
| Criterion | Target | Result |
|---|---|---|
| QuixBugs recall | ≥ 25% | **30%** ✅ |
| Holdout precision | ≥ 85% (from 66.7%) | **100%** ✅ |
| Holdout recall | ≥ 16.7% | **16.7%** ✅ |
| Corrected-BFS holdout FP removed | yes | **removed** ✅ |

---

## 4. False-positive change

- **Eliminated:** the Phase 84 holdout false positive on a corrected BFS. It
  came from `bfs_missing_visited_tracking` / `graph_traversal_cycle_handling`
  firing on a correct acyclic traversal that legitimately omits a visited set.
  Both rules are retired; the replacement asserts nothing about visited sets.
- **Did not introduce** any QuixBugs FP: the new rule's `while`-only restriction
  prevents it from firing on the correct `rpn_eval.py` / `shunting_yard.py`
  auxiliary-stack `for` loops. QuixBugs precision stays 100%.
- **Corrected BFS verdict** (`while queue:`): `termination_depends_on_consumed_container
  == True` ⇒ not flagged — same source file, fact-level separation from the buggy
  `while True:` variant.

---

## 5. Remaining name-bound rules (not in scope this phase)

These still match on function names / variable shapes and are candidates for a
future dataflow rewire (Phase 88+). Listed so the debt is explicit:

**`semantic_reasoning.py`**
- `bfs_queue_exhaustion`, `bfs_fifo_violation`, `bfs_cycle_handling` (gated on the
  `bfs` profile + `queue`/`seen`/`visited` name markers)
- `recursive_interval_not_shrinking` (name == `binsearch`, file == `find_in_sorted`)
- `recursive_euclidean_state_not_rotated` (name == `gcd`)
- `recursive_singleton_base_case_missing` (name == `mergesort`)
- `recursive_empty_choice_base_case_missing` (name == `possible_change`)
- `recursive_identity_base_case` (name == `subsequences`)
- `dijkstra_relaxes_from_destination`, `floyd_warshall_recurrence_direction`,
  `bellman_ford_updates_edge_weight` (name == `shortest_path*`)
- `counting_sort_reconstructs_from_input` (name == `bucketsort`),
  `heap_window_reprocesses_seed` (name == `kheapsort`),
  `quicksort_drops_duplicate_values` (name == `quicksort`)
- `recursive_progress_invariant` (uses the `recursion` profile)

**`bug_intelligence/patterns.py` — `algorithm_mismatch`**
- DFS branch (`"depth_first"`/`"dfs"`), binary-search branch, factorial /
  fibonacci / gcd branches (all name-matched)

Note: `bfs_queue_exhaustion` is intentionally retained to protect in-domain
recall; the new name-free rule is what makes the renamed BFS still flag. The two
overlap only on named BFS in-domain.

---

## 6. Boundaries honored

- No new bug categories (one consolidating finding replaces four retirements).
- Recall not chased — the `while`-only restriction traded a marginal in-domain
  TP for clean precision.
- No QuixBugs-specific heuristics added; detection is structural.
- No changes to voice / browser / trading / website / router / memory.
- No target repositories modified; QuixBugs read-only.
- Read-only, local, deterministic, no LLM.

---

## 7. Verification commands

```
py -3 -m pytest builder_core/tests/ -q                                  # 60 passed
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs  # P=100% R=30%
py -3 scripts/run_phase84_holdout_benchmark.py                           # holdout P=100% R=16.7% FP=0
```
