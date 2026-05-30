# Phase 83C QuixBugs Gap Analysis

Date: 2026-05-30

## Scope

This is a report-only analysis. No semantic rules were implemented.

Command run:

```powershell
py -3 -m builder_core.cli benchmark-quixbugs --project C:\Repos\QuixBugs
```

Current output:

```text
buggy files analyzed: 50
correct files analyzed: 50
true positives: 1
false positives: 0
precision: 1.0000
recall: 0.0200
true positive rate: 0.0200
false positive rate: 0.0000
```

The one semantic true positive is `breadth_first_search.py`. Its unconditional
`while True` loop consumes `queue.popleft()` without terminating when the
frontier is empty, so an unreachable goal raises instead of returning `False`.

## Benchmark Hygiene Finding

The current paired benchmark treats every top-level `*.py` pair as a buggy
algorithm. Ten of the 50 pairs are companion test harnesses or shared support
files, not algorithm positives:

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

Eight are identical between buggy and corrected trees. The other two contain a
harness-only change or whitespace-only change. They should eventually be
excluded from the benchmark denominator before recall is used as a release
gate. The raw benchmark baseline is `1/50 = 2.0%`; the algorithm-only baseline
is `1/40 = 2.5%`.

## Missed Bug Inventory

The following inventory covers every raw benchmark miss. Actual bugs are
inferred by comparing `python_programs/` with `correct_python_programs/`.

Risk scale:

- `Low`: profile-gated rule with a narrow invariant and strong evidence.
- `Medium`: useful invariant, but valid alternative implementations exist.
- `High`: likely to overfit unless tests or multiple structural signals agree.
- `N/A`: benchmark-noise entry; filter it rather than add a semantic rule.

| Missed file | Algorithm category | Actual bug inferred from corrected pair | Why the analyzer missed it | Candidate semantic profile or rule | Generality | FP risk |
| --- | --- | --- | --- | --- | --- | --- |
| `bitcount.py` | Bit manipulation | Uses `n ^= n - 1` instead of `n &= n - 1`; the bit-clearing loop can fail to make progress. | No bit-count identity profile or loop-state progress proof. | Bit-count profile: each iteration must clear at least one set bit and converge toward zero. | General for Kernighan-style bit count | Medium |
| `breadth_first_search_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `bucketsort.py` | Sorting | Reconstructs output by enumerating `arr` instead of bucket `counts`, using input values as repetition counts. | Sorting profile does not reason about count-array production and consumption. | Counting-sort profile: reconstruction must iterate the bucket-count array and preserve input cardinality. | General for counting and bucket sort | Low |
| `depth_first_search.py` | Graph traversal / DFS | Never records visited nodes before recursive expansion, so cycles recurse repeatedly. | Existing semantic DFS support is not yet connected to a recursive visited-state invariant. | DFS profile: every expanded node must enter visited state before recursive neighbor traversal. | General | Low |
| `depth_first_search_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `detect_cycle.py` | Linked-list traversal | Dereferences `hare.successor` before checking whether `hare` is `None`; odd-length acyclic lists can raise. | No tortoise-hare null-safety profile or dereference guard analysis. | Linked-list cycle profile: guard the fast pointer before every one-step or two-step dereference. | General | Low |
| `detect_cycle_test.py` | Companion harness | Harness-only delta removes a questionable manual case; it is not the algorithm mutation. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `find_first_in_sorted.py` | Binary search | Uses `while lo <= hi` even though `hi = len(arr)` is exclusive; absent values can access `arr[len(arr)]`. | No binary-search interval-contract profile. | Binary-search profile: exclusive upper bounds require `lo < hi`; prove midpoint remains in range. | General | Low |
| `find_in_sorted.py` | Binary search / recursion | Upper-half recursion calls `binsearch(mid, end)` instead of `binsearch(mid + 1, end)`, so the interval may not shrink. | Generic recursion checks only look for a base-case return, not argument progress. | Recursive interval profile: every recursive branch must strictly shrink `[start, end)`. | General | Low |
| `flatten.py` | Recursive traversal / generator | Scalar leaves yield `flatten(x)` generator objects instead of yielding `x`. | No recursive generator leaf-shape profile. | Flatten profile: recurse only for container nodes; yield scalar leaves directly. | General for flattening traversals | Medium |
| `gcd.py` | Euclidean recursion | Recurses as `gcd(a % b, b)` instead of `gcd(b, a % b)`, so state may not progress. | No Euclidean algorithm profile or recursive-argument descent rule. | GCD profile: recursive state rotates divisor and remainder; remainder must decrease. | General | Low |
| `get_factors.py` | Recursive factorization | Returns `[]` when no divisor below `n` is found, losing a prime residual factor; corrected result is `[n]`. | No terminal-residue rule for recursive factorization. | Factorization profile: if no proper divisor is found and `n > 1`, emit the residual prime. | General | Low |
| `hanoi.py` | Recursive planning | Records the main disk move as `(start, helper)` instead of `(start, end)`. | No Hanoi recurrence profile. | Hanoi profile: recurrence is move substack to helper, move root disk to destination, move substack to destination. | General for Hanoi, narrow domain | Low |
| `is_valid_parenthesization.py` | Stack-depth validation | Returns `True` after iteration even when unmatched opening parentheses leave `depth > 0`. | No terminal-balance invariant. | Delimiter-balance profile: reject negative prefixes and require terminal depth zero. | General | Low |
| `kheapsort.py` | Heap sorting | Heapifies `arr[:k]` and then iterates all of `arr`, duplicating the initial window; corrected loop uses `arr[k:]`. | No sort cardinality or sliding-window consumption rule. | Heap-window sort profile: seed elements must not be consumed again; yielded cardinality must equal input cardinality. | General | Low |
| `knapsack.py` | Dynamic programming | Uses `weight < j` instead of `weight <= j`, excluding exact-fit items. | No exact-capacity boundary invariant for knapsack transitions. | Knapsack profile: include-item transition is allowed when `weight <= capacity`. | General | Low |
| `kth.py` | Selection / divide and conquer | Recursing into the upper partition keeps `k` unchanged instead of subtracting the lower-and-pivot partition size. | No quickselect rank-rebasing profile. | Quickselect profile: rebase rank when descending into the upper partition. | General | Low |
| `lcs_length.py` | Dynamic programming | Character-match transition reads `dp[i - 1, j] + 1` instead of diagonal `dp[i - 1, j - 1] + 1`. | No DP recurrence template for common substring/subsequence tables. | LCS-length profile: a character match advances both axes and uses the diagonal predecessor. | General for LCS-style DP | Low |
| `levenshtein.py` | Recursive dynamic programming | Matching first characters incorrectly add one edit cost. | No edit-distance recurrence profile. | Levenshtein profile: equal leading characters advance both inputs at zero added cost. | General | Low |
| `lis.py` | Dynamic programming / sequence | Assigns `longest = length + 1`, allowing the global best length to decrease; corrected code takes `max`. | No monotonic aggregate-state invariant. | LIS profile: global best length must be monotonically non-decreasing. | General | Low |
| `longest_common_subsequence.py` | Recursive dynamic programming | On a character match, advances `a` but not `b`, allowing the same character in `b` to be reused. | No paired-sequence consumption invariant. | LCS profile: a matched character consumes one element from both sequences. | General | Low |
| `max_sublist_sum.py` | Dynamic programming / Kadane | Never resets the running sum after a negative prefix, so later optimal sublists can be suppressed. | No Kadane recurrence profile. | Maximum-subarray profile: running state is clamped or restarted when carrying the prefix is worse. | General | Low |
| `mergesort.py` | Sorting / recursion | Base case handles only empty arrays. A singleton splits into itself recursively and does not terminate. | Generic recursion sees a conditional return but does not prove coverage for the minimum non-empty input. | Divide-and-conquer sort profile: base case must cover lengths `0` and `1`; recursive partitions must shrink. | General | Low |
| `minimum_spanning_tree.py` | Graph / union-find | Merges component members with `.update()` instead of assigning a shared representative set; component aliases diverge after later unions. | No union-find equivalence-class consistency profile. | Union-find profile: all members of a merged component must resolve to the same representative or shared set. | General | Medium |
| `minimum_spanning_tree_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `next_palindrome.py` | Numeric sequence transformation | Overflow case emits one extra zero by multiplying with `len(digit_list)` instead of `len(digit_list) - 1`. | No output-length invariant for palindromic carry expansion. | Next-palindrome profile: all-9 overflow increases digit count by exactly one and preserves palindrome symmetry. | General for palindrome increment | Medium |
| `next_permutation.py` | Permutation algorithm | Successor comparison is reversed, selecting an element smaller than the pivot instead of the rightmost greater element. | No next-permutation profile. | Next-permutation profile: pivot swap candidate must be greater than the pivot and suffix must be reversed. | General | Low |
| `node.py` | Shared support type | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts shared support as a positive. | Benchmark manifest or support-file exclusion. | General benchmark hygiene | N/A |
| `pascal.py` | Dynamic programming / combinatorics | Builds row `r` with `range(0, r)` instead of `range(0, r + 1)`, dropping the right edge. | No row-shape invariant. | Pascal profile: row `r` must contain `r + 1` entries and start/end with `1`. | General | Low |
| `possible_change.py` | Recursive dynamic programming | Does not stop when `coins` is empty; destructuring `first, *rest = coins` can fail on impossible branches. | Base-case detection does not prove all structurally reachable terminal states are covered. | Recursive enumeration profile: handle empty-choice state before destructuring or indexing. | General | Low |
| `powerset.py` | Recursive enumeration | Returns only subsets containing `first`, omitting the branch that excludes it. | No include/exclude completeness invariant. | Powerset profile: combine both recursive branches; output cardinality should be `2 ** len(arr)`. | General | Low |
| `quicksort.py` | Sorting | Partitions with `< pivot` and `> pivot`, dropping values equal to the pivot. | Sorting profile does not check multiset preservation across partitions. | Quicksort profile: partition branches plus pivot must preserve duplicate cardinality. | General | Low |
| `reverse_linked_list.py` | Linked-list traversal | Never assigns `prevnode = node`; the reversed prefix is not advanced and the result is `None`. | No loop-carried state progression profile for linked-list reversal. | Linked-list reversal profile: save next, redirect link, advance previous, advance current. | General | Low |
| `reverse_linked_list_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `rpn_eval.py` | Stack evaluation | Pops right operand before left operand and calls `op(token, a, b)`; subtraction and division use reversed operands. | No stack-machine operand-role profile. | RPN profile: for binary operators, second pop is left operand and first pop is right operand. | General | Low |
| `shortest_path_length.py` | Shortest path / Dijkstra | Candidate distance adds edge length to the existing destination lookup instead of the popped source `distance`. | Shortest-path profile exists declaratively but has no relaxation data-flow check. | Dijkstra profile: relax `distance[u] + weight(u, v)` into destination `v`. | General | Low |
| `shortest_path_length_test.py` | Companion harness | Whitespace-only harness delta; no algorithm bug. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `shortest_path_lengths.py` | All-pairs shortest path / Floyd-Warshall | Recurrence uses `length[i, k] + length[j, k]` instead of `length[i, k] + length[k, j]`. | No Floyd-Warshall recurrence profile. | Floyd-Warshall profile: intermediary transition must compose `i -> k` with `k -> j`. | General | Low |
| `shortest_path_lengths_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `shortest_paths.py` | Shortest path / Bellman-Ford | Writes relaxed values into `weight_by_edge[u, v]` instead of destination state `weight_by_node[v]`. | No Bellman-Ford assignment-target check. | Bellman-Ford profile: each relaxation updates destination distance state, not edge weights. | General | Low |
| `shortest_paths_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `shunting_yard.py` | Parsing / stack algorithm | Never pushes encountered operators onto `opstack`, so operators disappear from output. | No token-conservation invariant for parser transforms. | Shunting-yard profile: every operator is either emitted or retained on the operator stack. | General | Low |
| `sieve.py` | Number theory | Uses `any(n % p > 0 for p in primes)`; with an empty initial prime list it never seeds `2`, and the logic should require no divisor. | No prime-sieve profile or vacuous-truth check. | Sieve profile: append candidate only if all prior primes do not divide it; seed behavior must accept `2`. | General | Low |
| `sqrt.py` | Numerical iteration / Newton-Raphson | Convergence checks `abs(x - approx)` instead of residual `abs(x - approx ** 2)`. | No numerical residual profile. | Newton square-root profile: stop based on squared residual or successive approximation delta. | General | Low |
| `subsequences.py` | Recursive enumeration | Base case for `k == 0` returns `[]` instead of `[[]]`, preventing recursive construction of valid sequences. | No combinatorial identity base-case rule. | Recursive enumeration profile: selecting zero remaining elements yields one empty selection. | General | Low |
| `to_base.py` | Numeric conversion | Appends least-significant digits to the right, reversing the representation. | No positional-conversion digit-order profile. | Base-conversion profile: remainders must be prepended or the accumulated output reversed. | General | Low |
| `topological_ordering.py` | Graph traversal / topological sort | Adds a node when ordered nodes cover its outgoing nodes instead of its incoming prerequisites. | No topological-order predecessor invariant. | Topological-sort profile: emit a node only after all incoming dependencies are satisfied. | General | Low |
| `topological_ordering_test.py` | Companion harness | No algorithm bug; buggy and corrected files are identical. | The benchmark glob counts a harness as a positive. | Benchmark filter: exclude `*_test.py`. | General benchmark hygiene | N/A |
| `wrap.py` | Text segmentation | Omits the final remaining `text` after the loop, dropping the last line. | No remainder-consumption invariant. | Segmentation profile: after iterative splitting, append the terminal remainder exactly once. | General | Low |

## Recommended Rule Ranking

The ranking below favors profile-gated checks with structural evidence. Catch
counts are counts of currently missed algorithm files, not support files.

| Rank | Recommended semantic rule family | Misses caught | Example files | Generality | FP risk | Difficulty | Why next |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| 1 | Recursive progress and terminal-state coverage | 6 | `find_in_sorted.py`, `gcd.py`, `get_factors.py`, `mergesort.py`, `possible_change.py`, `subsequences.py` | High | Low | Medium | Extends the existing recursion profile from "base case exists" to "all recursive branches shrink and terminal identities are covered." |
| 2 | Shortest-path and DP relaxation data flow | 6 | `knapsack.py`, `lcs_length.py`, `lis.py`, `shortest_path_length.py`, `shortest_path_lengths.py`, `shortest_paths.py` | High | Low | Medium | The existing profiles already name these invariants; adding profile-specific transition checks produces precise findings. |
| 3 | Collection cardinality and element-preservation invariants | 5 | `bucketsort.py`, `kheapsort.py`, `powerset.py`, `quicksort.py`, `wrap.py` | High | Low-Medium | Medium | Detects dropped, duplicated, or unconsumed elements in transformations. Test expectations can reduce ambiguity. |
| 4 | Graph and linked-structure traversal state invariants | 5 | `depth_first_search.py`, `detect_cycle.py`, `minimum_spanning_tree.py`, `reverse_linked_list.py`, `topological_ordering.py` | High | Low-Medium | Medium | Generalizes the successful BFS approach: track state needed for termination and correctness. |
| 5 | Boundary-shape and exact-fit invariants | 4 | `find_first_in_sorted.py`, `knapsack.py`, `next_palindrome.py`, `pascal.py` | High | Low | Low-Medium | Narrow profile checks catch boundary defects while avoiding broad off-by-one warnings. |
| 6 | Paired-sequence consumption and recurrence invariants | 3 | `lcs_length.py`, `levenshtein.py`, `longest_common_subsequence.py` | High | Low | Medium | Matching two inputs should advance both or consume zero edit cost according to the named algorithm. |
| 7 | Stack-machine and parser token-conservation rules | 2 | `rpn_eval.py`, `shunting_yard.py` | Medium-High | Low | Medium | Both rules are strong because token roles and conservation are explicit in stack algorithm profiles. |
| 8 | Domain comparison-direction rules | 2 | `next_permutation.py`, `sieve.py` | Medium | Low | Low | Named algorithms provide enough context to validate comparison direction safely. |
| 9 | Numerical-method residual and monotonic-progress rules | 2 | `bitcount.py`, `sqrt.py` | Medium-High | Medium | Medium | Useful beyond QuixBugs, but should require a recognized algorithm profile before reporting. |
| 10 | Recursive planning and leaf-output rules | 2 | `flatten.py`, `hanoi.py` | Medium | Medium | Medium | Valuable but narrower than the preceding families and more sensitive to alternative implementations. |

Some files appear under more than one family because multiple rule designs
could detect the same defect. Implementation planning should deduplicate by
file when calculating projected recall.

## Precision-Preserving Implementation Tranche

The first tranche should target narrow, low-risk checks from the top-ranked
families:

1. Recursive interval shrinkage and terminal-state coverage:
   `find_in_sorted.py`, `gcd.py`, `mergesort.py`, `possible_change.py`,
   `subsequences.py`.
2. Profile-specific shortest-path relaxations:
   `shortest_path_length.py`, `shortest_path_lengths.py`, `shortest_paths.py`.
3. Sorting multiset/cardinality preservation:
   `bucketsort.py`, `kheapsort.py`, `quicksort.py`.

This tranche adds 11 unique algorithm true positives. Including the existing
BFS true positive:

```text
raw current denominator:        12 / 50 = 24.0% recall
algorithm-only denominator:     12 / 40 = 30.0% recall
```

That reaches the requested 20-30% range while keeping the proposed checks
profile-gated and structurally explainable. The benchmark-hygiene filter should
be implemented before using the adjusted recall figure as a release metric.

## Guardrails For The Next Pass

- Keep profile detection explicit; do not report recurrence defects from loose
  vocabulary alone.
- Require AST evidence and, where available, indexed-test evidence.
- Test every new rule against both `python_programs/` and
  `correct_python_programs/`.
- Treat corrected-file findings as regressions unless manually justified.
- Add benchmark filtering separately from semantic-rule work so metric changes
  remain auditable.
- Avoid literal source matching or QuixBugs filename-only rules. Filenames may
  select a general algorithm profile, but findings must follow from behavior.
