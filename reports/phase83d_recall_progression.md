# Phase 83D Recall Progression

Date: 2026-05-30

## Scope

Phase 83D implemented only the first recall-expansion tranche approved in the
Phase 83C gap analysis:

1. recursive interval shrinkage and terminal coverage
2. shortest-path relaxations
3. sorting multiset and cardinality preservation

No other semantic rule family was added.

## Benchmark Command

The benchmark was run after each rule family:

```powershell
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

The QuixBugs evaluator now excludes ten support or companion-harness pairs:

```text
breadth_first_search_test.py
depth_first_search_test.py
detect_cycle_test.py
minimum_spanning_tree_test.py
node.py
reverse_linked_list_test.py
shortest_path_length_test.py
shortest_path_lengths_test.py
shortest_paths_test.py
topological_ordering_test.py
```

This changes the benchmark denominator from 50 top-level Python pairs to 40
algorithm pairs. The filter does not change semantic analysis behavior.

## Recall Progression

| Checkpoint | True positives | False positives | Precision | Recall | Newly detected buggy files |
| --- | ---: | ---: | ---: | ---: | --- |
| Algorithm-only baseline | 1 / 40 | 0 / 40 | 1.0000 | 0.0250 | Existing `breadth_first_search.py` |
| After recursion rules | 6 / 40 | 0 / 40 | 1.0000 | 0.1500 | `find_in_sorted.py`, `gcd.py`, `mergesort.py`, `possible_change.py`, `subsequences.py` |
| After shortest-path rules | 9 / 40 | 0 / 40 | 1.0000 | 0.2250 | `shortest_path_length.py`, `shortest_path_lengths.py`, `shortest_paths.py` |
| After sorting/cardinality rules | 12 / 40 | 0 / 40 | 1.0000 | 0.3000 | `bucketsort.py`, `kheapsort.py`, `quicksort.py` |

## Added Rules

### Recursive Interval Shrinkage And Terminal Coverage

| Rule | Detected file | Invariant |
| --- | --- | --- |
| `recursive_interval_not_shrinking` | `find_in_sorted.py` | Upper-half binary-search recursion must advance to `mid + 1`. |
| `recursive_euclidean_state_not_rotated` | `gcd.py` | Euclidean recursion must rotate to `gcd(b, a % b)`. |
| `recursive_singleton_base_case_missing` | `mergesort.py` | Merge sort must stop for both empty and singleton inputs. |
| `recursive_empty_choice_base_case_missing` | `possible_change.py` | Recursive enumeration must handle an empty choice list before destructuring it. |
| `recursive_identity_base_case` | `subsequences.py` | Selecting zero remaining elements has one identity result: `[[]]`. |

### Shortest-Path Relaxations

| Rule | Detected file | Invariant |
| --- | --- | --- |
| `dijkstra_relaxes_from_destination` | `shortest_path_length.py` | Dijkstra relaxation must add edge weight to the popped source distance. |
| `floyd_warshall_recurrence_direction` | `shortest_path_lengths.py` | Floyd-Warshall must compose `i -> k` with `k -> j`. |
| `bellman_ford_updates_edge_weight` | `shortest_paths.py` | Bellman-Ford must update destination distance state, not the immutable edge table. |

### Sorting Multiset And Cardinality Preservation

| Rule | Detected file | Invariant |
| --- | --- | --- |
| `counting_sort_reconstructs_from_input` | `bucketsort.py` | Output reconstruction must enumerate bucket counts, not raw input values. |
| `heap_window_reprocesses_seed` | `kheapsort.py` | Elements seeded into the heap must not be streamed through it a second time. |
| `quicksort_drops_duplicate_values` | `quicksort.py` | Partition comparisons must preserve values equal to the pivot. |

## Final Benchmark Output

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
```

## Outcome

Phase 83C predicted a move from `1 / 40` to `12 / 40`. Phase 83D reached that
prediction exactly:

```text
before:  1 / 40 =  2.5% recall
after:  12 / 40 = 30.0% recall
change: +11 true positives
```

The success condition is satisfied because recall is at least 20%. The failure
condition is not triggered because precision remains above 0.80.
