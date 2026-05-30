# Phase 90 — Rule Migration Table

**Date:** 2026-05-30
**Context:** Unification of the analysis stacks behind one engine. This table
records the status of every detector/rule and which unified-engine stage now
owns it.

## Legend (status)

- **fact-backed** — decision is made from data-flow / value-flow / taint facts
  (the generalizing target state).
- **active-general** — structural AST rule, name-agnostic, runs on all repos.
- **legacy** — name/shape-bound rule retained because it still carries
  in-domain recall; surfaced through the engine but flagged for future rewrite.
- **quarantined (benchmark-specific)** — matches an exact QuixBugs function
  name / variable shape; kept only so in-domain recall does not regress; **must
  not** be cited as general capability.
- **deleted** — removed in a prior phase.

## Engine ownership (pipeline stage)

- **SecurityAgent** ← `security.py` over `valueflow` taint facts
- **LogicBugAgent** ← `patterns.py` (incl. the `dataflow`-backed rule)
- **AlgorithmAgent** ← `semantic_reasoning.py` (wrapped as one detector source)

---

## Security & value (fact-backed) — SecurityAgent

| Rule | Status | Category | Source facts |
|---|---|---|---|
| code_injection (eval/exec) | fact-backed | security_risk | taint source→sink |
| command_injection (subprocess/os.system, shell=True) | fact-backed | security_risk | taint + shell flag |
| sql_injection (built-string execute) | fact-backed | security_risk | taint into execute() |
| path_traversal (tainted open) | fact-backed | security_risk | taint into open(), sanitizer check |
| unsafe_deserialization (pickle/yaml) | fact-backed | security_risk | taint into loader |
| weak_crypto (md5/sha1) | fact-backed | security_risk | sensitive-call catalog |
| null_dereference | fact-backed | logic_bug | nullability lattice + guard narrowing |

## Logic / structure — LogicBugAgent

| Rule | Status | Category | Notes |
|---|---|---|---|
| unguarded_container_consumption | **fact-backed** | logic_bug | data-flow loop facts (Phase 87) |
| inconsistent_return | active-general | logic_bug | migrated — fact-aware via returns |
| off_by_one | active-general | logic_bug | migrated (range(len()+1), inclusive bound) |
| mutation_while_iterating | active-general | logic_bug | migrated |
| unreachable_code | active-general | logic_bug | migrated |
| recursion_no_termination | active-general | logic_bug | migrated |
| suspicious_conditional | active-general | logic_bug | constant/while-True, self-compare |
| impossible_condition | active-general | logic_bug | contradiction / unsatisfiable range |
| duplicated_branches | active-general | logic_bug | identical if/else |
| reversed_comparison | active-general (low conf) | logic_bug | min/max selection heuristic |
| exception_swallowed | active-general | logic_bug | `except: pass`/`continue` |
| unused_result | active-general | logic_bug | discarded pure expression |
| shadowed_name | active-general | maintainability | builtin / param shadow |
| unused_variable | active-general | maintainability | assigned-never-read |
| untested_module / untested_function | active-general | test_gap | advisory only |

## Algorithm-name family — `algorithm_mismatch` (LogicBugAgent)

| Branch | Status | Category | Notes |
|---|---|---|---|
| BFS branch | **deleted** (Phase 87) | — | replaced by unguarded_container_consumption |
| DFS / binary_search / factorial / fibonacci / gcd | quarantined (benchmark-specific) | algorithm_bug | name-matched; kept but flagged for rewrite |

## Semantic algorithm invariants — AlgorithmAgent (legacy)

| Rule | Status | Category | Notes |
|---|---|---|---|
| bfs_queue_exhaustion | legacy | algorithm_bug | name-bound; retained for in-domain BFS recall |
| bfs_fifo_violation | legacy | algorithm_bug | name-bound (queue/pop shape) |
| bfs_cycle_handling | legacy | algorithm_bug | name-bound (visited markers) |
| recursive_interval_not_shrinking | quarantined (benchmark-specific) | algorithm_bug | name==binsearch, file==find_in_sorted |
| recursive_euclidean_state_not_rotated | quarantined (benchmark-specific) | algorithm_bug | name==gcd |
| recursive_singleton_base_case_missing | quarantined (benchmark-specific) | algorithm_bug | name==mergesort |
| recursive_empty_choice_base_case_missing | quarantined (benchmark-specific) | algorithm_bug | name==possible_change |
| recursive_identity_base_case | quarantined (benchmark-specific) | algorithm_bug | name==subsequences |
| dijkstra_relaxes_from_destination | quarantined (benchmark-specific) | algorithm_bug | name==shortest_path_length |
| floyd_warshall_recurrence_direction | quarantined (benchmark-specific) | algorithm_bug | name==shortest_path_lengths |
| bellman_ford_updates_edge_weight | quarantined (benchmark-specific) | algorithm_bug | name==shortest_paths |
| counting_sort_reconstructs_from_input | quarantined (benchmark-specific) | algorithm_bug | name==bucketsort |
| heap_window_reprocesses_seed | quarantined (benchmark-specific) | algorithm_bug | name==kheapsort |
| quicksort_drops_duplicate_values | quarantined (benchmark-specific) | algorithm_bug | name==quicksort |
| recursive_progress_invariant | legacy | algorithm_bug | profile-based, general-ish |

## Deleted (prior phases)

| Rule | Phase | Reason |
|---|---|---|
| bfs_frontier_termination | 87 | replaced by name-free unguarded_container_consumption |
| bfs_missing_visited_tracking | 87 | false-universal invariant → holdout false positives |
| graph_traversal_cycle_handling | 87 | false-universal invariant → holdout false positives |

---

## Summary

- **Fact-backed:** 8 rules (7 security/value + unguarded_container_consumption).
- **Active-general:** ~14 structural logic/maintainability/test-gap rules.
- **Legacy (name-bound, retained):** 4 (bfs_*, recursive_progress_invariant).
- **Quarantined (benchmark-specific):** ~13 exact-name algorithm rules + the
  remaining `algorithm_mismatch` name branches.
- **Deleted:** 3 (Phase 87).

The quarantined set is the honest technical debt: it props up the in-domain
QuixBugs recall (30%) and is the explicit target of the next rewrite onto
value/interprocedural facts. It is isolated to the AlgorithmAgent and clearly
labeled so it is never mistaken for general capability.
