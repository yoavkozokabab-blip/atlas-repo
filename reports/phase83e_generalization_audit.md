# Phase 83E Generalization Audit

Date: 2026-05-30

## Scope

This is an audit-only pass. No new bug rules were implemented.

The current analyzer was run against the algorithm-only QuixBugs pairs:

```powershell
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

The benchmark excludes ten companion harness or shared-support pairs identified
during Phase 83C:

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

## Exact Benchmark Output

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

## Confusion Report

| Metric | Value |
| --- | ---: |
| True positives | 12 |
| False positives | 0 |
| False negatives | 28 |
| True negatives | 40 |
| Precision | 1.0000 |
| Recall | 0.3000 |
| False-positive rate | 0.0000 |
| Accuracy | 0.6500 |

All 40 corrected algorithm files were analyzed. None produced a semantic
finding.

## True Positives

Each current finding is grounded in a named algorithm invariant and disappears
on the corresponding corrected implementation.

| Buggy file | Detected rule | Actual bug | Why detection is valid |
| --- | --- | --- | --- |
| `breadth_first_search.py` | `bfs_queue_exhaustion` | Uses `while True` around `queue.popleft()`, so an unreachable target empties the deque and raises instead of returning `False`. | BFS must terminate when its frontier is empty. Indexed tests also expect `False` for an unreachable graph. |
| `bucketsort.py` | `counting_sort_reconstructs_from_input` | Reconstructs output by enumerating raw `arr` instead of bucket `counts`. | Counting-style bucket sort must emit each bucket index with its recorded frequency. Reading input values as frequencies violates cardinality and value preservation. |
| `find_in_sorted.py` | `recursive_interval_not_shrinking` | Upper-half recursion calls `binsearch(mid, end)` rather than `binsearch(mid + 1, end)`. | When `mid == start`, the recursive interval does not shrink. Recursive binary search requires strict progress toward its base case. |
| `gcd.py` | `recursive_euclidean_state_not_rotated` | Recurses as `gcd(a % b, b)` rather than `gcd(b, a % b)`. | Euclid's algorithm rotates divisor and remainder. Keeping `b` fixed can prevent descent toward zero. |
| `kheapsort.py` | `heap_window_reprocesses_seed` | Seeds the heap from `arr[:k]`, then iterates all of `arr` instead of `arr[k:]`. | The seed window is consumed twice, so output cardinality exceeds input cardinality. Sliding-window heap sort must continue after the seeded prefix. |
| `mergesort.py` | `recursive_singleton_base_case_missing` | Stops only for empty arrays, not singleton arrays. | A singleton splits into a recursive branch containing itself. Divide-and-conquer sorting must terminate for lengths zero and one. |
| `possible_change.py` | `recursive_empty_choice_base_case_missing` | Destructures `first, *rest = coins` without handling an empty choice list. | Impossible branches can exhaust `coins`. Recursive enumeration must return zero before destructuring an empty list. |
| `quicksort.py` | `quicksort_drops_duplicate_values` | Uses strict `< pivot` and `> pivot`, dropping values equal to the pivot. | Sorting must preserve the input multiset. Equal values enter neither partition and are lost. |
| `shortest_path_length.py` | `dijkstra_relaxes_from_destination` | Adds edge length to an existing destination lookup rather than the popped source `distance`. | Dijkstra relaxation must evaluate `distance[u] + weight(u, v)` before updating `v`. |
| `shortest_path_lengths.py` | `floyd_warshall_recurrence_direction` | Uses `length[i, k] + length[j, k]` rather than `length[i, k] + length[k, j]`. | Floyd-Warshall composes an incoming segment to `k` with an outgoing segment from `k`. |
| `shortest_paths.py` | `bellman_ford_updates_edge_weight` | Writes relaxation output into `weight_by_edge[u, v]` rather than destination state `weight_by_node[v]`. | Bellman-Ford relaxes vertex-distance state. Mutating edge weights corrupts the graph and leaves destination distances stale. |
| `subsequences.py` | `recursive_identity_base_case` | Returns `[]` for `k == 0` rather than `[[]]`. | Choosing zero remaining items has one identity selection, the empty list. Recursive callers need that result to construct longer selections. |

## Corrected Programs Flagged

None.

| Corrected file | Rule | Assessment |
| --- | --- | --- |
| `(none)` | `(none)` | All 40 corrected algorithm files remain semantic true negatives. |

## False Negatives

The remaining 28 buggy algorithms require semantic families not included in
Phase 83D.

| Missed buggy file | Actual bug | Why current analyzer missed it | Reasoning needed |
| --- | --- | --- | --- |
| `bitcount.py` | Uses `n ^= n - 1` instead of `n &= n - 1`; the bit-clearing loop does not implement the expected state reduction. | No bit-count profile or bitwise progress model. | Numerical loop-state progress for recognized Kernighan-style bit counting. |
| `depth_first_search.py` | Omits `nodesvisited.add(node)` before recursive neighbor expansion, so cycles can recurse repeatedly. | BFS visited-state reasoning exists, but recursive DFS visited-state reasoning is not implemented. | Graph-traversal state invariant: mark an expanded node before recursive traversal. |
| `detect_cycle.py` | Dereferences `hare.successor` without guarding `hare is None`, failing on some acyclic lists. | No pointer-dereference safety reasoning for tortoise-hare traversal. | Linked-list traversal state and null-guard analysis. |
| `find_first_in_sorted.py` | Uses `while lo <= hi` while `hi = len(arr)` is exclusive, allowing `arr[len(arr)]`. | Recursive binary-search progress is covered; iterative interval contracts are not. | Boundary-shape reasoning for inclusive versus exclusive search intervals. |
| `flatten.py` | Scalar leaves yield `flatten(x)` generator objects instead of yielding `x`. | No generator leaf-shape reasoning. | Recursive tree/list traversal: recurse only on containers and emit scalar leaves directly. |
| `get_factors.py` | Returns `[]` when no smaller divisor exists, losing the residual prime factor. | Recursive terminal-coverage checks do not yet model factorization residuals. | Domain terminal-state reasoning: emit the remaining prime when no proper divisor is found. |
| `hanoi.py` | Emits `(start, helper)` for the main disk move instead of `(start, end)`. | No Hanoi recurrence profile. | Recursive planning recurrence with source, helper, and destination role tracking. |
| `is_valid_parenthesization.py` | Returns `True` even when unmatched opening parentheses leave positive final depth. | No terminal accumulator invariant for delimiter matching. | Stack-depth validation: reject negative prefixes and require final depth zero. |
| `knapsack.py` | Uses `weight < j` instead of `weight <= j`, excluding exact-fit items. | Phase 83D shortest-path relaxation rules did not add DP boundary checks. | Dynamic-programming transition boundary reasoning. |
| `kth.py` | Upper-partition recursion keeps `k` unchanged rather than subtracting the skipped lower-and-pivot partition size. | Generic recursive progress does not model rank rebasing. | Selection-partition invariant: rebase rank when descending into the upper partition. |
| `lcs_length.py` | Match recurrence reads `dp[i - 1, j] + 1` instead of diagonal `dp[i - 1, j - 1] + 1`. | No LCS table-recurrence profile. | Paired-sequence DP recurrence: a match advances both axes. |
| `levenshtein.py` | Equal leading characters incorrectly add one edit cost. | No edit-distance recurrence profile. | Paired-sequence recursion: equal characters advance both inputs at zero cost. |
| `lis.py` | Assigns `longest = length + 1`, allowing the global optimum to decrease. | No monotonic aggregate-state analysis. | DP state monotonicity: global best values must not regress. |
| `longest_common_subsequence.py` | On a character match, advances `a` but not `b`, allowing reuse of the same character in `b`. | No paired-sequence consumption invariant. | Matched-symbol recursion must consume both sequences. |
| `max_sublist_sum.py` | Carries negative prefixes instead of restarting or clamping the running sum. | No Kadane recurrence profile. | Dynamic-programming recurrence for restart-versus-extend decisions. |
| `minimum_spanning_tree.py` | Updates component sets rather than assigning a shared merged representative, allowing alias divergence. | No union-find equivalence-class model. | Graph component consistency and representative-alias reasoning. |
| `next_palindrome.py` | Overflow case emits one extra zero by multiplying with `len(digit_list)` instead of `len(digit_list) - 1`. | No output-shape invariant for numeric carry expansion. | Boundary-shape reasoning: all-9 overflow grows palindrome length by exactly one. |
| `next_permutation.py` | Swap-candidate comparison is reversed, selecting a smaller candidate instead of a greater successor. | No next-permutation profile. | Domain comparison-direction rule for successor selection. |
| `pascal.py` | Builds row `r` with `range(0, r)` instead of `range(0, r + 1)`, dropping the right edge. | No combinatorial row-shape invariant. | Structural output-shape reasoning: Pascal row `r` has `r + 1` entries. |
| `powerset.py` | Returns only subsets including `first`, omitting the exclude branch. | Recursive identity coverage exists for subsequences, but branch-completeness reasoning is absent. | Include/exclude recurrence completeness and expected cardinality `2 ** n`. |
| `reverse_linked_list.py` | Never advances `prevnode = node`, so the reversed prefix is lost and the result is `None`. | No loop-carried state model for linked-list reversal. | Linked-structure mutation sequence: save next, redirect link, advance previous, advance current. |
| `rpn_eval.py` | Pops operands and applies them in reverse order for subtraction and division. | No stack-machine operand-role reasoning. | Stack evaluation profile: second pop is the left operand, first pop is the right operand. |
| `shunting_yard.py` | Never pushes encountered operators onto `opstack`, so operators disappear. | No parser token-conservation reasoning. | Transformation conservation: each operator is emitted or retained on the operator stack. |
| `sieve.py` | Uses `any(n % p > 0 for p in primes)` instead of requiring no divisor; empty-prime-list behavior prevents seeding. | No prime-sieve quantifier profile. | Domain quantifier and vacuous-truth reasoning. |
| `sqrt.py` | Convergence checks `abs(x - approx)` instead of square residual `abs(x - approx ** 2)`. | No numerical-method residual model. | Newton-method convergence invariant. |
| `to_base.py` | Appends least-significant remainders to the right, reversing output digit order. | No positional-conversion accumulator-direction profile. | Numeric conversion reasoning: prepend digits or reverse at completion. |
| `topological_ordering.py` | Tests whether outgoing nodes are ordered instead of checking incoming prerequisites. | No topological-order dependency-direction profile. | Graph dependency invariant: emit only after all incoming prerequisites are satisfied. |
| `wrap.py` | Fails to append the final unsplit remainder after the loop. | Cardinality rules currently target sorting, not segmentation. | Remainder-consumption reasoning for iterative segmentation. |

## Generalization Assessment

### Verdict

The Phase 83D result is **semantically valid on QuixBugs paired corrections,
but not yet independently proven to generalize across unrelated repositories**.

It is not merely a syntactic-score improvement:

- Every reported true positive explains an algorithm invariant violation.
- Every finding disappears on the paired corrected implementation.
- No corrected algorithm file is flagged.
- The rules do not compare against corrected source text at runtime.
- The rules do not execute target code or rely on QuixBugs tests being present,
  except that BFS enriches its explanation with indexed-test evidence.

There is still controlled specialization:

- Several rules are selected by recognizable algorithm function names.
- Some checks assume conventional variable roles such as `mid`, `end`,
  `weight_by_edge`, or `pivot`.
- The audit dataset remains QuixBugs itself; it is not an external holdout.

The current result should therefore be described as **robust within the paired
QuixBugs corpus, precision-preserving, and meaningfully semantic, with
cross-repository generalization still requiring a separate holdout corpus**.

## Success-Criteria Assessment

| Criterion | Result |
| --- | --- |
| Precision `>= 0.80` | Pass: `1.0000` |
| Recall `>= 0.25` | Pass: `0.3000` |
| False-positive rate acceptable | Pass: `0.0000` on 40 corrected algorithms |
| Clearly identify next families | Pass: ranked below |

## Top Five Next Rule Families

No new rules were implemented in this audit. The next best candidates are:

| Rank | Rule family | Likely catches | Example misses | Generalization value | Estimated FP risk |
| --- | ---: | --- | --- | --- | --- |
| 1 | Paired-sequence DP and recursive consumption invariants | 3 | `lcs_length.py`, `levenshtein.py`, `longest_common_subsequence.py` | High: common sequence algorithms with crisp transition roles | Low |
| 2 | Graph and linked-structure traversal state invariants | 4 | `depth_first_search.py`, `detect_cycle.py`, `reverse_linked_list.py`, `topological_ordering.py` | High: visited state, null guards, dependency direction, and loop-carried pointer state recur in production code | Low-Medium |
| 3 | Boundary-shape and exact-fit invariants | 4 | `find_first_in_sorted.py`, `knapsack.py`, `next_palindrome.py`, `pascal.py` | High: off-by-one defects with profile-specific boundaries | Low |
| 4 | Stack-machine and token-conservation rules | 2 | `rpn_eval.py`, `shunting_yard.py` | Medium-High: clear operand-role and token-conservation invariants | Low |
| 5 | Recursive branch-completeness and residual-result invariants | 3 | `get_factors.py`, `kth.py`, `powerset.py` | High: catches missing terminal values, omitted branches, and rank rebasing | Low-Medium |

## Recommended Next Validation Step

Before adding more QuixBugs rules, build a small holdout benchmark of unrelated
correct and intentionally buggy implementations for the existing 12 rules.
Require the same precision floor (`>= 0.80`) on that holdout. This will measure
whether conventional variable-role assumptions are too narrow or too brittle
outside QuixBugs.
