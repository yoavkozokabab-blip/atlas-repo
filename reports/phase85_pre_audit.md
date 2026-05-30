# Phase 85 — Pre-Audit: Semantic Rule Inventory

Date: 2026-05-30

## Scope

Evidence-only audit of Builder Core Bug Intelligence semantic layer.

**Inspected (no code changes):**

- `builder_core/semantic_reasoning.py`
- `builder_core/algorithm_profiles.py`
- `builder_core/benchmark.py`

**Benchmark commands used to collect metrics:**

```powershell
cd C:\J.A.R.V.I.S\local_jarvis
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
py -3 scripts/run_phase84_holdout_benchmark.py
```

QuixBugs denominator: **40 algorithm pairs** (10 support/harness pairs excluded per
`benchmark.py::_is_algorithm_pair`). Holdout denominator: **12 paired cases**
(`builder_core/benchmarks/holdout/`).

Ground-truth convention (`benchmark.py`): a **file-level true positive** is any
semantic finding on a buggy file; a **false positive** is any semantic finding on the
paired fixed file. Multiple rules on one file still count as one TP/FP file.

---

## Executive Summary

| Metric | Value |
| --- | ---: |
| **Total semantic rules** | **18** |
| **Algorithm profiles** | 8 |
| **QuixBugs TP files** | 12 / 40 (recall 0.30, precision 1.00) |
| **QuixBugs FP files** | 0 / 40 |
| **Rules contributing ≥1 QuixBugs TP** | **12 / 18** |
| **Rules contributing zero QuixBugs TP** | **6 / 18** |
| **Holdout FP files** | 1 / 12 (precision 0.67 on holdout) |
| **Rules contributing holdout FP** | **2** (`bfs_missing_visited_tracking`, `graph_traversal_cycle_handling`) |

The semantic layer is **highly tuned to QuixBugs naming and structure**. Twelve rules
each explain exactly one QuixBugs buggy file. Six rules never fire on the QuixBugs
corpus at all but two of those fire on holdout **correct** code — the primary
generalization risk.

---

## 1. Counts

### 1.1 Total rules

**18 semantic rules** emitted from `semantic_reasoning.py` (all `kind: "semantic"`).

### 1.2 QuixBugs true-positive contribution

| Rule | QuixBugs TP files | Buggy file |
| --- | ---: | --- |
| `bfs_queue_exhaustion` | 1 | `breadth_first_search.py` |
| `counting_sort_reconstructs_from_input` | 1 | `bucketsort.py` |
| `recursive_interval_not_shrinking` | 1 | `find_in_sorted.py` |
| `recursive_euclidean_state_not_rotated` | 1 | `gcd.py` |
| `heap_window_reprocesses_seed` | 1 | `kheapsort.py` |
| `recursive_singleton_base_case_missing` | 1 | `mergesort.py` |
| `recursive_empty_choice_base_case_missing` | 1 | `possible_change.py` |
| `quicksort_drops_duplicate_values` | 1 | `quicksort.py` |
| `dijkstra_relaxes_from_destination` | 1 | `shortest_path_length.py` |
| `floyd_warshall_recurrence_direction` | 1 | `shortest_path_lengths.py` |
| `bellman_ford_updates_edge_weight` | 1 | `shortest_paths.py` |
| `recursive_identity_base_case` | 1 | `subsequences.py` |

**Sum:** 12 TP files, 12 distinct rules (one primary rule per detected buggy file).

### 1.3 Holdout false-positive contribution

| Rule | Holdout FP files | Fixed case |
| --- | ---: | --- |
| `bfs_missing_visited_tracking` | 1 | `transfer_bfs_empty_queue/fixed.py` |
| `graph_traversal_cycle_handling` | 1 | `transfer_bfs_empty_queue/fixed.py` |

**Sum:** 1 FP file, **2 rule-level false positives** (same file flagged twice).

Note: `bfs_queue_exhaustion` and `recursive_euclidean_state_not_rotated` also fire on
holdout **buggy** cases (transfer success). `bfs_missing_visited_tracking` and
`graph_traversal_cycle_handling` also fire on the holdout **buggy** BFS (ancillary
findings alongside the true `bfs_queue_exhaustion` hit).

---

## 2. Algorithm Profiles (`algorithm_profiles.py`)

Profiles gate which semantic check families run. Detection matches **function name,
docstring, or function body text** against word-boundary regex patterns.

| Profile | Patterns (sample) | Invariants declared | Rules that consume profile |
| --- | --- | --- | --- |
| `bfs` | `breadth_first_search`, `bfs` | FIFO frontier, exhaustion, visited | `_bfs_findings` (5 rules) |
| `dfs` | `depth_first_search`, `dfs` | stack/recursive DFS, visited | `_generic_profile_findings` → `graph_traversal_cycle_handling` |
| `shortest_path` | `shortest_path`, `dijkstra`, `bellman_ford` | distance monotonicity | (no profile-gated rules; rules use function names instead) |
| `sorting` | `sort`, `quicksort`, `mergesort`, `kheapsort`, … | ordering, cardinality | (rules use function names instead) |
| `recursion` | `recursive`, `recursion`, `recurse` | base case, progress | `recursive_progress_invariant` |
| `graph_traversal` | `graph`, `neighbor`, `adjacent`, … | cycle handling | `graph_traversal_cycle_handling` |
| `tree_traversal` | `tree`, `preorder`, `inorder`, … | empty tree, visit order | *(no dedicated rules)* |
| `dynamic_programming` | `memo`, `knapsack`, `lcs`, … | tabulation, base rows | *(no dedicated rules)* |

**Observation:** `shortest_path`, `sorting`, `tree_traversal`, and `dynamic_programming`
profiles are detected but most Phase 83D rules **ignore profiles** and instead key off
**QuixBugs function names** (`quicksort`, `mergesort`, `shortest_path_length`, etc.).

---

## 3. Benchmark Wiring (`benchmark.py`)

| Aspect | Behavior |
| --- | --- |
| Input | Local QuixBugs checkout: `python_programs/` vs `correct_python_programs/` |
| Exclusions | `*_test.py`, `node.py` |
| Analysis | `analyze_python()` with indexed `python_testcases/` as `test_documents` |
| Metric filter | Only findings with `kind == "semantic"` |
| TP | Buggy file has ≥1 semantic finding |
| FP | Correct file has ≥1 semantic finding |
| Special case | Report always prints `breadth_first_search` detail |

Test expectations (`extract_test_expectations`) strengthen BFS rules when testcase text
contains phrases like `"unconnected"`, `"not found"`, `"unreachable"` — **QuixBugs
testcase coupling**.

---

## 4. Full Semantic Rule Catalog

For each rule: name, purpose, files analyzed, benchmark contribution, false-positive risk.

Severity shown as implemented.

---

### 4.1 BFS family (`_bfs_findings` — requires `bfs` profile)

#### `bfs_queue_exhaustion` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Detect `while True` loops that call `popleft()` without queue-empty guard — classic empty-deque crash / missing not-found return. |
| **Files analyzed** | Any function with `bfs` profile (name/doc/body matches `breadth_first_search`, `bfs`, …). |
| **QuixBugs TP** | **1** — `python_programs/breadth_first_search.py` |
| **Holdout FP** | **0** on fixed files |
| **FP risk** | **Medium** — legitimate BFS with `while True` + internal break/return before empty dequeue would still flag; mitigated somewhat by requiring `popleft`. Test expectation text amplifies message on QuixBugs. |

#### `bfs_frontier_termination` (medium)

| Field | Detail |
| --- | --- |
| **Purpose** | BFS loop exists with `popleft` but loop test does not reference queue truthiness/length. |
| **Files analyzed** | Same as BFS profile. |
| **QuixBugs TP** | **0** |
| **Holdout FP** | **0** |
| **FP risk** | **High** — any non-`while queue` termination pattern (sentinel, flag, nested break) triggers; never validated on QuixBugs. |

#### `bfs_fifo_violation` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Queue uses `pop()` (LIFO) instead of `popleft()` (FIFO). |
| **Files analyzed** | BFS-profile functions with queue-named deque/list. |
| **QuixBugs TP** | **0** (QuixBugs DFS/other bugs use different patterns) |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — intentional stack-as-queue didactic code; rare in production. |

#### `bfs_missing_visited_tracking` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Frontier grows via `append`/`extend` but no `seen`/`visited` identifier exists. |
| **Files analyzed** | BFS-profile functions. |
| **QuixBugs TP** | **0** |
| **Holdout FP** | **1** — correct minimal BFS (`transfer_bfs_empty_queue/fixed.py`) |
| **FP risk** | **Very high** — **proven holdout FP**; many correct small-graph BFS implementations omit explicit visited sets when graph is acyclic or dedup happens elsewhere. |

#### `bfs_cycle_handling` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | A `visited`/`seen` name exists but no membership filter (`in` / `not in`) guards frontier growth. |
| **Files analyzed** | BFS-profile functions with visited-like identifiers. |
| **QuixBugs TP** | **0** |
| **Holdout FP** | **0** |
| **FP risk** | **High** — visited tracking via separate structure, bitmask, or external graph API invisible to AST heuristics. |

---

### 4.2 Recursive family (`_recursive_findings` — function/path coupled)

#### `recursive_interval_not_shrinking` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Binary search upper-half call uses `binsearch(mid, end)` instead of advancing lower bound. |
| **Files analyzed** | Function named **`binsearch`** in file stem **`find_in_sorted`** only. |
| **QuixBugs TP** | **1** — `find_in_sorted.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Low on QuixBugs** — **extreme name coupling** limits blast radius; low risk outside exact QuixBugs shape. |

#### `recursive_euclidean_state_not_rotated` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | GCD recursion passes `(a % b, b)` keeping divisor fixed instead of `(b, a % b)`. |
| **Files analyzed** | Function named **`gcd`** (any file). |
| **QuixBugs TP** | **1** — `gcd.py` |
| **Holdout TP** | **1** — `transfer_gcd_no_rotate` (transfer success) |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — flags any recursive `gcd(..., b)` where second arg is literally `b`; alternate Euclidean formulations or helper wrappers may false-positive. |

#### `recursive_singleton_base_case_missing` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Merge sort recurses without visible singleton-length guard on first parameter. |
| **Files analyzed** | Function named **`mergesort`**. |
| **QuixBugs TP** | **1** — `mergesort.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — `_covers_singleton_length` heuristic may miss valid guards expressed as `len <= 1` elsewhere; any function named `mergesort` is in scope. |

#### `recursive_empty_choice_base_case_missing` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Coin-change recursion unpacks `coins` without empty-list guard before destructuring. |
| **Files analyzed** | Function named **`possible_change`**. |
| **QuixBugs TP** | **1** — `possible_change.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Low–medium** — tightly coupled to QuixBugs `possible_change` structure. |

#### `recursive_identity_base_case` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Subsequence builder returns `[]` for `k == 0` instead of identity `[[]]`. |
| **Files analyzed** | Function named **`subsequences`**. |
| **QuixBugs TP** | **1** — `subsequences.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Low** — requires exact `k == 0` branch returning empty list literal; QuixBugs-specific. |

---

### 4.3 Shortest-path family (`_shortest_path_findings` — function-name coupled)

#### `dijkstra_relaxes_from_destination` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Relaxation adds edge weight to `.get()` destination lookup instead of popped source distance. |
| **Files analyzed** | Function named **`shortest_path_length`**. |
| **QuixBugs TP** | **1** — `shortest_path_length.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — pattern requires `length_by_edge` subscript + `.get()` in same `BinOp`; QuixBugs variable names baked in. |

#### `floyd_warshall_recurrence_direction` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Floyd-Warshall adds `length[i,k] + length[j,k]` instead of `length[i,k] + length[k,j]`. |
| **Files analyzed** | Function named **`shortest_path_lengths`**. |
| **QuixBugs TP** | **1** — `shortest_path_lengths.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — requires exact subscript index names `i,j,k` and array `length_by_path`. |

#### `bellman_ford_updates_edge_weight` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Bellman-Ford writes relaxed weight into `weight_by_edge[...]` via `min()` instead of vertex distance state. |
| **Files analyzed** | Function named **`shortest_paths`**. |
| **QuixBugs TP** | **1** — `shortest_paths.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Medium** — keyed on `weight_by_edge` identifier from QuixBugs. |

---

### 4.4 Sorting / cardinality family (`_sorting_cardinality_findings`)

#### `counting_sort_reconstructs_from_input` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Bucket sort reconstruct phase iterates raw `arr` with `extend` instead of bucket counts. |
| **Files analyzed** | Function named **`bucketsort`**. |
| **QuixBugs TP** | **1** — `bucketsort.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Low–medium** — requires `for ... in enumerate(arr)` + `extend` pattern inside `bucketsort`. |

#### `heap_window_reprocesses_seed` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | K-heapsort seeds `arr[:k]` then iterates full `arr`, double-processing prefix. |
| **Files analyzed** | Function named **`kheapsort`**. |
| **QuixBugs TP** | **1** — `kheapsort.py` |
| **Holdout FP** | **0** |
| **FP risk** | **Low** — needs both `arr[:k]` slice and `for ... in arr`; QuixBugs-shaped. |

#### `quicksort_drops_duplicate_values` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Partition uses strict `< pivot` and `> pivot`, dropping equal elements. |
| **Files analyzed** | Function named **`quicksort`** with comparisons on identifiers **`x`** and **`pivot`**. |
| **QuixBugs TP** | **1** — `quicksort.py` |
| **Holdout FP** | **0** (synthetic transfer case did **not** trigger — pattern mismatch) |
| **FP risk** | **Medium** — any `quicksort` using `x`/`pivot` strict compares flags; Dutch-flag or three-way partition not recognized. |

---

### 4.5 Generic profile family (`_generic_profile_findings`)

#### `recursive_progress_invariant` (high)

| Field | Detail |
| --- | --- |
| **Purpose** | Recursive function under `recursion` profile lacks any `if` branch containing `return` (no visible base case). |
| **Files analyzed** | Any function matching `recursion` profile patterns in name/doc/body. |
| **QuixBugs TP** | **0** |
| **Holdout FP** | **0** |
| **FP risk** | **Very high** — many correct recursive functions use implicit tail structure, helper dispatch, or returns outside direct `if` children; **never measured on QuixBugs**. |

#### `graph_traversal_cycle_handling` (medium)

| Field | Detail |
| --- | --- |
| **Purpose** | DFS or `graph_traversal` profile code appends to frontier without visited set. |
| **Files analyzed** | Functions with `dfs` or `graph_traversal` profile. |
| **QuixBugs TP** | **0** (`depth_first_search.py` missed — separate bug family) |
| **Holdout FP** | **1** — correct BFS fixed file (profile overlap: BFS also matches `graph` tokens via neighbors) |
| **FP risk** | **Very high** — **proven holdout FP**; overlaps BFS visited logic; fires on acyclic traversals. |

---

## 5. Duplicated / Overlapping Logic

### 5.1 Visited-set / cycle detection (triple overlap)

| Rule | Trigger |
| --- | --- |
| `bfs_missing_visited_tracking` | BFS profile + append + no visited **name** |
| `bfs_cycle_handling` | BFS profile + visited **name** + no `in`/`not in` filter |
| `graph_traversal_cycle_handling` | DFS/graph profile + append + no visited **name** |

Same underlying invariant (*“graph expansion needs cycle guard”*) implemented three
times with slightly different profile gates. Holdout proved **`bfs_missing_visited_tracking`**
and **`graph_traversal_cycle_handling`** can both fire on the **same correct file**.

### 5.2 Recursive base-case coverage (split across four rules)

| Rule | Coupling |
| --- | --- |
| `recursive_singleton_base_case_missing` | `mergesort` + length heuristics |
| `recursive_empty_choice_base_case_missing` | `possible_change` + unpack pattern |
| `recursive_identity_base_case` | `subsequences` + `k==0` return shape |
| `recursive_progress_invariant` | generic recursion profile |

No shared helper for “terminal case visible before recursive call”; each QuixBugs bug
has a bespoke detector.

### 5.3 Profile declared but bypassed

`shortest_path` and `sorting` profiles are detected in `algorithm_profiles.py` but
Phase 83D rules in `_shortest_path_findings` and `_sorting_cardinality_findings` key
almost entirely on **function names** (`shortest_path_length`, `quicksort`, …) rather
than profile membership — duplicated conceptual model (profile vs name gate).

### 5.4 Test-expectation amplification (BFS only)

`extract_test_expectations()` reads QuixBugs `python_testcases/` indexed by **file stem**
match. Only BFS rules consume `related_tests` in messages. This ties semantic messaging
to QuixBugs test corpus wording (`unconnected`, `branching graph`, etc.).

---

## 6. QuixBugs Naming / Structure Coupling

Rules ranked by coupling strength:

| Coupling level | Rules |
| --- | --- |
| **Function name + file stem** | `recursive_interval_not_shrinking` (`binsearch` + `find_in_sorted`) |
| **Function name only (QuixBugs exports)** | `mergesort`, `possible_change`, `subsequences`, `bucketsort`, `kheapsort`, `quicksort`, `shortest_path_length`, `shortest_path_lengths`, `shortest_paths`, `gcd` |
| **QuixBugs variable names in AST** | `length_by_edge`, `length_by_path`, `weight_by_edge`, `x`/`pivot`, `arr`, `k` |
| **Profile + QuixBugs function name** | `bfs_queue_exhaustion` (`breadth_first_search` profile match) |
| **Indexed testcase text** | BFS rules (expectation note appended from `python_testcases/`) |

**Implication:** Renaming QuixBugs functions or variables would silently disable most
rules even if the bug remained.

---

## 7. Rules With Zero QuixBugs TP (dead weight on benchmark)

These **6 rules never fire** on the 40 QuixBugs buggy algorithm files:

1. `bfs_frontier_termination`
2. `bfs_fifo_violation`
3. `bfs_missing_visited_tracking`
4. `bfs_cycle_handling`
5. `recursive_progress_invariant`
6. `graph_traversal_cycle_handling`

Two of these (`bfs_missing_visited_tracking`, `graph_traversal_cycle_handling`) **do**
fire on holdout — including a **false positive on correct code**. They add out-of-domain
risk without in-domain recall benefit.

---

## 8. Top 10 Highest False-Positive Risk Rules

Ranked by evidence: proven holdout FP > structural overbreadth > QuixBugs-only coupling
(low external blast radius).

| Rank | Rule | Risk rationale | Evidence |
| ---: | --- | --- | --- |
| 1 | `bfs_missing_visited_tracking` | Flags any BFS without visited **identifier** | **Holdout FP on correct BFS** |
| 2 | `graph_traversal_cycle_handling` | Generic append-without-visited on graph/dfs profiles | **Holdout FP on correct BFS**; 0 QuixBugs TP |
| 3 | `recursive_progress_invariant` | Any recursive profile fn without visible `if`/return base | 0 QuixBugs TP; extremely broad AST heuristic |
| 4 | `bfs_frontier_termination` | Punishes non-standard loop exit patterns | 0 QuixBugs TP; medium severity still surfaces in rankings |
| 5 | `bfs_cycle_handling` | Requires explicit `in`/`not in` on visited names | Visited via sets with different patterns missed; 0 QuixBugs TP |
| 6 | `quicksort_drops_duplicate_values` | Only understands strict two-way partition on `x`/`pivot` | Would FP on valid 3-way partition quicksorts named `quicksort` |
| 7 | `recursive_singleton_base_case_missing` | Name == `mergesort` + incomplete length guard detection | Any alternate mergesort guard syntax false-flags |
| 8 | `dijkstra_relaxes_from_destination` | Hard-coded `length_by_edge` + `.get()` shape | Unrelated Dijkstra impls with different naming escape; wrong naming false-flags |
| 9 | `floyd_warshall_recurrence_direction` | Requires exact `i,j,k` index names | Any renamed FW implementation false-flags |
| 10 | `recursive_euclidean_state_not_rotated` | Literal `b` as second recursive arg | Transfer TP proves value, but non-standard gcd signatures could FP |

**Lower risk (tightly QuixBugs-coupled):** `recursive_interval_not_shrinking`,
`recursive_empty_choice_base_case_missing`, `recursive_identity_base_case`,
`heap_window_reprocesses_seed`, `counting_sort_reconstructs_from_input` — unlikely to
fire outside QuixBugs-shaped code **because coupling limits reach, not because logic is
general**.

---

## 9. Pre-Audit Recommendations (informational only — no implementation)

1. **Do not expand QuixBugs-named rules** until holdout precision ≥ 0.90 (Phase 84 finding).
2. **Merge or tighten** the triple visited/cycle rules before adding graph coverage for
   `depth_first_search.py` FN.
3. **Require profile + structural gate** consistently — stop bypassing profiles with raw
   function-name checks, or drop unused profiles to reduce false confidence.
4. **Split benchmark reporting** to rule-level TP/FP tables (current file-level metric
   hides ancillary FP rules on buggy files).
5. **Retire or gate** the six zero–QuixBugs-TP rules behind stricter preconditions before
   any recall expansion.

---

## 10. Artifact Confirmation

- **No source code modified** in this pass.
- Report generated from static inspection + benchmark re-run on 2026-05-30.
