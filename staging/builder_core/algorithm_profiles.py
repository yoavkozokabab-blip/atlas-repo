"""Algorithm profiles used by Builder Core semantic reasoning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class AlgorithmProfile:
    name: str
    patterns: Tuple[str, ...]
    invariants: Tuple[str, ...]


PROFILES: Tuple[AlgorithmProfile, ...] = (
    AlgorithmProfile(
        "bfs",
        ("breadth_first_search", "breadth first search", "bfs"),
        (
            "frontier uses FIFO semantics",
            "frontier exhaustion terminates with not-found",
            "visited nodes are tracked before repeated expansion",
            "cycles do not cause repeated traversal",
        ),
    ),
    AlgorithmProfile(
        "dfs",
        ("depth_first_search", "depth first search", "dfs"),
        (
            "frontier uses stack or recursive depth-first semantics",
            "visited nodes prevent repeated traversal in cyclic graphs",
        ),
    ),
    AlgorithmProfile(
        "shortest_path",
        ("shortest_path", "shortest path", "dijkstra", "bellman_ford", "a_star"),
        (
            "distance state is updated monotonically",
            "unreachable destinations have an explicit outcome",
        ),
    ),
    AlgorithmProfile(
        "sorting",
        (
            "sort",
            "bucketsort",
            "quicksort",
            "quick_sort",
            "mergesort",
            "merge_sort",
            "heapsort",
            "kheapsort",
        ),
        (
            "result ordering matches the comparator",
            "partition or merge steps preserve every input element",
        ),
    ),
    AlgorithmProfile(
        "recursion",
        ("recursive", "recursion", "recurse"),
        (
            "a reachable base case exists",
            "recursive calls make progress toward the base case",
        ),
    ),
    AlgorithmProfile(
        "graph_traversal",
        ("graph", "traversal", "successor", "neighbor", "adjacent"),
        (
            "cycles are handled explicitly",
            "visited nodes are not expanded repeatedly",
        ),
    ),
    AlgorithmProfile(
        "tree_traversal",
        ("tree", "preorder", "inorder", "postorder", "level_order"),
        (
            "empty trees have an explicit outcome",
            "children are visited in the advertised order",
        ),
    ),
    AlgorithmProfile(
        "dynamic_programming",
        ("dynamic_programming", "dynamic programming", "memo", "knapsack", "lcs", "levenshtein"),
        (
            "subproblems are reused or tabulated",
            "base rows or base cases cover empty input",
        ),
    ),
)


def detect_profiles(function_name: str, docstring: str = "", source_text: str = "") -> list[AlgorithmProfile]:
    """Return profiles that match function metadata or source vocabulary."""
    haystack = " ".join((function_name, docstring or "", source_text or "")).lower()
    matched: list[AlgorithmProfile] = []
    for profile in PROFILES:
        if any(re.search(rf"\b{re.escape(pattern)}\b", haystack) for pattern in profile.patterns):
            matched.append(profile)
    return matched


def profile_names(profiles: Iterable[AlgorithmProfile]) -> list[str]:
    return [profile.name for profile in profiles]
