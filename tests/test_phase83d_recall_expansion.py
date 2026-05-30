"""Phase 83D first recall-expansion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from builder_core.benchmark import evaluate_quixbugs
from builder_core.python_analysis import analyze_python


def _semantic_rules(path: str, source: str) -> set[str]:
    return {
        item["rule"]
        for item in analyze_python(path, source)["findings"]
        if item.get("kind") == "semantic"
    }


@pytest.mark.parametrize(
    ("path", "rule", "buggy", "correct"),
    [
        (
            "find_in_sorted.py",
            "recursive_interval_not_shrinking",
            """\
def find_in_sorted(arr, x):
    def binsearch(start, end):
        mid = (start + end) // 2
        if x > arr[mid]:
            return binsearch(mid, end)
        return -1
    return binsearch(0, len(arr))
""",
            """\
def find_in_sorted(arr, x):
    def binsearch(start, end):
        mid = (start + end) // 2
        if x > arr[mid]:
            return binsearch(mid + 1, end)
        return -1
    return binsearch(0, len(arr))
""",
        ),
        (
            "gcd.py",
            "recursive_euclidean_state_not_rotated",
            """\
def gcd(a, b):
    if b == 0:
        return a
    return gcd(a % b, b)
""",
            """\
def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)
""",
        ),
        (
            "mergesort.py",
            "recursive_singleton_base_case_missing",
            """\
def mergesort(arr):
    if len(arr) == 0:
        return arr
    middle = len(arr) // 2
    return mergesort(arr[:middle]) + mergesort(arr[middle:])
""",
            """\
def mergesort(arr):
    if len(arr) <= 1:
        return arr
    middle = len(arr) // 2
    return mergesort(arr[:middle]) + mergesort(arr[middle:])
""",
        ),
        (
            "possible_change.py",
            "recursive_empty_choice_base_case_missing",
            """\
def possible_change(coins, total):
    if total == 0:
        return 1
    if total < 0:
        return 0
    first, *rest = coins
    return possible_change(coins, total - first) + possible_change(rest, total)
""",
            """\
def possible_change(coins, total):
    if total == 0:
        return 1
    if total < 0 or not coins:
        return 0
    first, *rest = coins
    return possible_change(coins, total - first) + possible_change(rest, total)
""",
        ),
        (
            "subsequences.py",
            "recursive_identity_base_case",
            """\
def subsequences(a, b, k):
    if k == 0:
        return []
    return [[x] + seq for x in range(a, b + 1) for seq in subsequences(x + 1, b, k - 1)]
""",
            """\
def subsequences(a, b, k):
    if k == 0:
        return [[]]
    return [[x] + seq for x in range(a, b + 1) for seq in subsequences(x + 1, b, k - 1)]
""",
        ),
        (
            "shortest_path_length.py",
            "dijkstra_relaxes_from_destination",
            """\
def shortest_path_length(length_by_edge, distance, node, nextnode, unvisited_nodes):
    return get(unvisited_nodes, nextnode) + length_by_edge[node, nextnode]
""",
            """\
def shortest_path_length(length_by_edge, distance, node, nextnode, unvisited_nodes):
    return distance + length_by_edge[node, nextnode]
""",
        ),
        (
            "shortest_path_lengths.py",
            "floyd_warshall_recurrence_direction",
            """\
def shortest_path_lengths(length_by_path, i, j, k):
    return length_by_path[i, k] + length_by_path[j, k]
""",
            """\
def shortest_path_lengths(length_by_path, i, j, k):
    return length_by_path[i, k] + length_by_path[k, j]
""",
        ),
        (
            "shortest_paths.py",
            "bellman_ford_updates_edge_weight",
            """\
def shortest_paths(weight_by_edge, weight_by_node, u, v, weight):
    weight_by_edge[u, v] = min(weight_by_node[u] + weight, weight_by_node[v])
""",
            """\
def shortest_paths(weight_by_edge, weight_by_node, u, v, weight):
    weight_by_node[v] = min(weight_by_node[u] + weight, weight_by_node[v])
""",
        ),
        (
            "bucketsort.py",
            "counting_sort_reconstructs_from_input",
            """\
def bucketsort(arr, k):
    counts = [0] * k
    sorted_arr = []
    for i, count in enumerate(arr):
        sorted_arr.extend([i] * count)
    return sorted_arr
""",
            """\
def bucketsort(arr, k):
    counts = [0] * k
    sorted_arr = []
    for i, count in enumerate(counts):
        sorted_arr.extend([i] * count)
    return sorted_arr
""",
        ),
        (
            "kheapsort.py",
            "heap_window_reprocesses_seed",
            """\
def kheapsort(arr, k):
    heap = arr[:k]
    for x in arr:
        yield x
""",
            """\
def kheapsort(arr, k):
    heap = arr[:k]
    for x in arr[k:]:
        yield x
""",
        ),
        (
            "quicksort.py",
            "quicksort_drops_duplicate_values",
            """\
def quicksort(arr):
    pivot = arr[0]
    lesser = [x for x in arr[1:] if x < pivot]
    greater = [x for x in arr[1:] if x > pivot]
    return lesser + [pivot] + greater
""",
            """\
def quicksort(arr):
    pivot = arr[0]
    lesser = [x for x in arr[1:] if x < pivot]
    greater = [x for x in arr[1:] if x >= pivot]
    return lesser + [pivot] + greater
""",
        ),
    ],
)
def test_first_tranche_rules_flag_buggy_but_not_corrected(
    path: str,
    rule: str,
    buggy: str,
    correct: str,
) -> None:
    assert rule in _semantic_rules(path, buggy)
    assert rule not in _semantic_rules(path, correct)


def test_quixbugs_benchmark_excludes_support_pairs(tmp_path: Path) -> None:
    buggy_root = tmp_path / "python_programs"
    correct_root = tmp_path / "correct_python_programs"
    buggy_root.mkdir()
    correct_root.mkdir()
    buggy_bfs = """\
from collections import deque
def breadth_first_search(start, goal):
    queue = deque([start])
    while True:
        node = queue.popleft()
        if node is goal:
            return True
"""
    correct_bfs = buggy_bfs.replace("while True:", "while queue:")
    for root, bfs in ((buggy_root, buggy_bfs), (correct_root, correct_bfs)):
        (root / "breadth_first_search.py").write_text(bfs, encoding="utf-8")
        (root / "node.py").write_text("class Node: pass\n", encoding="utf-8")
        (root / "breadth_first_search_test.py").write_text("assert True\n", encoding="utf-8")

    report = evaluate_quixbugs(str(tmp_path))

    assert report["buggy_files_analyzed"] == 1
    assert report["correct_files_analyzed"] == 1
    assert report["excluded_pairs"] == ["breadth_first_search_test.py", "node.py"]


@pytest.mark.skipif(
    not Path(r"C:\Repos\QuixBugs\python_programs").is_dir(),
    reason="local QuixBugs checkout is unavailable",
)
def test_local_quixbugs_first_tranche_reaches_projected_recall() -> None:
    report = evaluate_quixbugs(r"C:\Repos\QuixBugs")

    assert report["buggy_files_analyzed"] == 40
    assert report["correct_files_analyzed"] == 40
    assert report["true_positives"] == 12
    assert report["false_positives"] == 0
    assert report["precision"] == 1.0
    assert report["recall"] == 0.3
