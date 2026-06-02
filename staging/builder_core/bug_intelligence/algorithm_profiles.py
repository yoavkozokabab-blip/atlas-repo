"""Algorithm profiles for semantic bug reasoning (Phase 83B).

A profile is declarative knowledge about what a *named* algorithm must do to be
correct. The semantic engine classifies a function to a profile, extracts
behavioral facts from its AST, and checks those facts against the profile's
invariants. Each violated invariant becomes an explained Finding.

This file holds only the knowledge (names + invariants + reasoning text). The
checking logic lives in ``semantic.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    keywords: Tuple[str, ...]
    invariants: Tuple[str, ...]
    summary: str = ""


# Order matters: more specific algorithms are matched before generic families.
PROFILES: List[Profile] = [
    Profile(
        key="bfs",
        title="Breadth-First Search",
        keywords=("breadth_first_search", "breadth_first", "bfs"),
        invariants=(
            "frontier is a FIFO queue (remove from the front: popleft / pop(0))",
            "loop terminates when the frontier is empty (e.g. `while queue:`)",
            "visited set with a membership test guards against revisiting on cycles",
        ),
        summary="BFS explores level by level using a FIFO frontier and stops when it empties.",
    ),
    Profile(
        key="dfs",
        title="Depth-First Search",
        keywords=("depth_first_search", "depth_first", "dfs"),
        invariants=(
            "frontier is LIFO (stack: pop() / pop(-1)) or the call stack (recursion)",
            "loop/recursion terminates (empty stack or base case)",
            "visited set with a membership test guards against revisiting on cycles",
        ),
        summary="DFS dives deep first using a LIFO stack or recursion.",
    ),
    Profile(
        key="shortest_path",
        title="Shortest Path",
        keywords=("shortest_path", "shortest_path_length", "dijkstra",
                  "bellman_ford", "floyd"),
        invariants=(
            "distances/costs are tracked and updated (relaxation)",
            "a comparison selects the smaller/closer candidate",
            "termination when all reachable nodes are settled",
        ),
        summary="Shortest-path routines relax edges, always keeping the minimal known cost.",
    ),
    Profile(
        key="sorting",
        title="Sorting",
        keywords=("sort", "quicksort", "mergesort", "bucketsort", "heapsort",
                  "kheapsort", "bubble_sort"),
        invariants=(
            "elements are compared",
            "elements are reordered (swaps, merge, or partition) so output is ordered",
            "output preserves the multiset of inputs (no elements lost or added)",
        ),
        summary="A sort compares elements and reorders them into nondecreasing order.",
    ),
    Profile(
        key="dynamic_programming",
        title="Dynamic Programming",
        keywords=("knapsack", "longest_common_subsequence", "lcs_length",
                  "levenshtein", "edit_distance", "possible_change", "lis",
                  "subsequences", "longest_increasing"),
        invariants=(
            "a memo/table caches subproblem results",
            "subproblems are combined via a recurrence",
            "table indices stay within bounds",
        ),
        summary="DP caches overlapping subproblems and combines them via a recurrence.",
    ),
    Profile(
        key="tree_traversal",
        title="Tree Traversal",
        keywords=("inorder", "preorder", "postorder", "levelorder",
                  "tree_traversal", "binary_tree"),
        invariants=(
            "every child is visited",
            "recursion or an explicit stack/queue drives the traversal",
            "traversal terminates at leaves (None children)",
        ),
        summary="A tree traversal visits each node exactly once in a defined order.",
    ),
    Profile(
        key="graph_traversal",
        title="Graph Traversal",
        keywords=("graph_search", "topological_ordering", "topological",
                  "detect_cycle", "reachable", "traverse", "minimum_spanning_tree"),
        invariants=(
            "a visited/seen set with a membership test prevents infinite loops on cycles",
            "every discovered neighbor is eventually processed",
            "termination when no unprocessed nodes remain",
        ),
        summary="Graph traversal must track visited nodes to stay finite on cyclic graphs.",
    ),
]

PROFILE_BY_KEY = {p.key: p for p in PROFILES}


def classify(function_name: str, file_stem: str) -> Profile | None:
    """Return the most specific matching Profile, or None."""
    haystack = f"{function_name.lower()} {file_stem.lower()}"
    for profile in PROFILES:  # specific-first ordering preserved
        for kw in profile.keywords:
            if kw in haystack:
                return profile
    return None
