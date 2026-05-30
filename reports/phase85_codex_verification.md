# Phase 85 Codex Verification

Date: 2026-05-30

## Scope

This is a verification-only pass. No production code was changed.

Inspected:

```text
builder_core/semantic_reasoning.py
builder_core/algorithm_profiles.py
builder_core/benchmark.py
reports/phase85_pre_audit.md
```

Executed:

```powershell
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
py -3 scripts/run_phase84_holdout_benchmark.py
py -3 -m pytest tests/test_phase83d_recall_expansion.py tests/test_phase83b_semantic_bug_reasoning.py tests/test_phase84_external_benchmark.py -q -p no:cacheprovider
```

## QuixBugs Benchmark

Exact output:

```text
QUIXBUGS BENCHMARK
buggy files analyzed: 40
correct files analyzed: 40
excluded support pairs: 10
true positives: 12
false positives: 0
precision: 1.0000
recall: 0.3000
true positive rate: 0.3000
false positive rate: 0.0000

BREADTH_FIRST_SEARCH
- [high] bfs_queue_exhaustion line 11: BFS appears incorrect because its traversal loop is unconditional (`while True`) while dequeuing with `popleft()`. When the frontier empties before finding the goal, it attempts to dequeue from an empty queue instead of terminating and returning False. Indexed tests expect False for an unreachable graph, so this violates the not-found behavior.
```

The Phase 83D QuixBugs result is reproducible:

```text
true positives:  12 / 40
false positives:  0 / 40
precision:        1.0000
recall:           0.3000
```

## External Holdout Benchmark

Exact output:

```text
EXTERNAL HOLDOUT BENCHMARK
cases analyzed: 12
true positives: 2
false positives: 1
false negatives: 10
true negatives: 11
precision: 0.6667
recall: 0.1667
accuracy: 0.5417

CASES WITH SEMANTIC FINDINGS ON BUGGY
- transfer_bfs_empty_queue [synthetic_transfer]: bfs_queue_exhaustion, bfs_missing_visited_tracking, graph_traversal_cycle_handling
- transfer_gcd_no_rotate [synthetic_transfer]: recursive_euclidean_state_not_rotated

FALSE POSITIVES ON FIXED
- transfer_bfs_empty_queue: bfs_missing_visited_tracking, graph_traversal_cycle_handling
```

The holdout precision drop is reproducible:

```text
QuixBugs precision: 1.0000
holdout precision:  0.6667
change:             -0.3333
```

Only two of the twelve buggy holdout cases receive semantic findings. The
transferred GCD rule is clean. The BFS queue-exhaustion rule transfers, but two
ancillary visited-state rules also flag the fixed BFS implementation.

## Focused Test Result

Exact result:

```text
........................                                                 [100%]
24 passed in 2.09s
```

The focused tests pass, but they do not establish an acceptable holdout
precision floor. `tests/test_phase84_external_benchmark.py` verifies corpus
availability and metric fields; it does not fail when holdout precision drops
below `0.80`.

## Risk Findings

### Proven Holdout False Positives

| Rule | Risk | Evidence |
| --- | --- | --- |
| `bfs_missing_visited_tracking` | High | Flags the corrected `transfer_bfs_empty_queue/fixed.py` because it requires an explicit `seen` or `visited` identifier. A BFS over an acyclic or externally deduplicated graph can be correct without that local identifier. |
| `graph_traversal_cycle_handling` | High | Flags the same corrected BFS because profile overlap classifies its neighbor expansion as graph traversal. It duplicates the visited-state assumption and adds no QuixBugs true positive. |

These two findings reduce holdout precision from a possible `1.0000` to
`0.6667`.

### Other High-Risk Rules

| Rule | Risk | Reason |
| --- | --- | --- |
| `recursive_progress_invariant` | High | Broad heuristic: a recursive-profile function without an `if` branch containing `return` is flagged. It contributes zero QuixBugs true positives and has not demonstrated holdout value. |
| `bfs_frontier_termination` | Medium-High | Treats non-standard BFS loop conditions as suspicious even when termination may be handled through a sentinel, nested break, or external iterator. It contributes zero QuixBugs true positives. |
| `bfs_cycle_handling` | Medium-High | Requires an explicit membership comparison involving a visited-like identifier. Correct deduplication through helper APIs, bitsets, or graph abstractions can be invisible to this AST pattern. |
| `quicksort_drops_duplicate_values` | Medium | Detects only literal `x` and `pivot` comparisons. The holdout transfer quicksort bug is missed because the implementation shape differs. |

### Duplicate Visited-State Logic

Three rules encode overlapping assumptions:

```text
bfs_missing_visited_tracking
bfs_cycle_handling
graph_traversal_cycle_handling
```

The holdout demonstrates that the overlap is not harmless: two rules flag the
same corrected file. This family should be tightened or gated before recall
expansion.

## Benchmark-Specific Rules

The Phase 83D rules perform real AST reasoning, but many are tightly coupled to
QuixBugs names and source shapes.

| Coupling | Rules or examples |
| --- | --- |
| Function name plus file stem | `recursive_interval_not_shrinking` requires helper `binsearch` inside file stem `find_in_sorted`. |
| Function-name dispatch | `mergesort`, `possible_change`, `subsequences`, `shortest_path_length`, `shortest_path_lengths`, `shortest_paths`, `bucketsort`, `kheapsort`, `quicksort`, `gcd`. |
| Literal variable roles | `length_by_edge`, `length_by_path`, `weight_by_edge`, `arr`, `k`, `x`, `pivot`, `mid`, `end`. |
| Indexed QuixBugs test wording | BFS message enrichment through test expectation extraction. |
| Benchmark-specific presentation | `benchmark.py` always prints a dedicated `BREADTH_FIRST_SEARCH` section. |

The strongest benchmark-specific rule is:

```text
recursive_interval_not_shrinking
```

It requires both the helper name `binsearch` and the file stem
`find_in_sorted`. This is useful for the QuixBugs case but is not a general
recursive interval analysis.

The shortest-path and sorting rules also have limited transfer reach because
they bypass the declared profiles and key directly on function names and
literal identifiers. Renaming variables can silently disable detection while
leaving the same defect intact.

## Hidden Source-Modification Risk

The benchmark execution path is read-only:

```text
builder_core/benchmark.py
  -> Path.read_text()
  -> analyze_python()
  -> ast.parse()
  -> semantic_reasoning.analyze_semantics()

builder_core/external_benchmark.py
  -> Path.read_text()
  -> json.loads()
  -> analyze_python()
```

No write, delete, rename, subprocess, or target-code execution path was found
in the benchmark flow.

A before/after SHA-256 snapshot was run around both evaluators:

```text
files_hashed=124
changed=[]
added=[]
removed=[]
```

The snapshot covered:

```text
C:\Repos\QuixBugs\python_programs\**\*.py
C:\Repos\QuixBugs\correct_python_programs\**\*.py
builder_core\benchmarks\holdout\pairs\**\*.py
```

`C:\Repos\QuixBugs` currently contains an untracked `.jarvis_builder/`
directory from earlier Builder Core indexing. The benchmark command used in
this audit does not write or refresh that directory. Running
`builder_core.cli init --project C:\Repos\QuixBugs` would write index metadata,
but that is outside the audited benchmark path.

## Git Diff --Name-Only

Command:

```powershell
git diff --name-only
```

Current tracked working-tree result:

```text
tracked_diff_count=10166
top_level_groups:
  data=9340
  reports=805
  voice=6
  conversation=5
  brain=2
  tests=1
  README.md=1
  .env.example=1
  tools=1
  agents=1
  config.py=1
  actions=1
  core=1

builder_core_tracked_diff:
(none; Builder Core files are currently untracked)
```

The complete `git diff --name-only` output is too large to inline usefully:
most entries are pre-existing generated runtime state under `data/` and
`reports/`. This audit did not modify those files.

Relevant untracked Phase 84 verification inputs:

```text
builder_core/benchmarks/holdout/manifest.json
builder_core/benchmarks/holdout/pairs/**/{buggy.py,fixed.py}
builder_core/external_benchmark.py
reports/phase85_pre_audit.md
scripts/run_phase84_holdout_benchmark.py
tests/test_phase84_external_benchmark.py
```

This Phase 85 pass adds only:

```text
reports/phase85_codex_verification.md
```

## Strategy Verdict

**Proceed with Phase 85 as a hardening and generalization phase, not as another
QuixBugs recall-expansion phase.**

Recommended order:

1. Gate or tighten `bfs_missing_visited_tracking` and
   `graph_traversal_cycle_handling`; they are proven holdout false positives.
2. Add a test that enforces a holdout precision floor of at least `0.80`.
3. Replace exact function-name and variable-name coupling with profile plus
   structural-role inference, one rule family at a time.
4. Measure rule-level true positives and false positives, not only file-level
   metrics.
5. Re-run QuixBugs and holdout benchmarks after every hardening change.

Do not add more QuixBugs-shaped rules until holdout precision is repaired.
