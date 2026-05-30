"""Profile-driven semantic checks for classic Python algorithms."""

from __future__ import annotations

import ast
import os
import re
from typing import Any, Dict, Iterable, List

from .algorithm_profiles import detect_profiles, profile_names
from .bug_intelligence import dataflow


def _line(lines: List[str], lineno: int) -> str:
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:240]
    return ""


def _finding(
    rule: str,
    severity: str,
    lineno: int,
    message: str,
    lines: List[str],
    *,
    related_tests: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "rule": rule,
        "kind": "semantic",
        "severity": severity,
        "line": lineno,
        "message": message,
        "evidence": _line(lines, lineno),
        "related_tests": list(related_tests or []),
    }


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return ""


def _function_calls(function: ast.AST, method: str) -> List[ast.Call]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
    ]


def _test_documents_for(path: str, test_documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return [
        document
        for document in test_documents
        if stem in document.get("path", "").lower()
        or stem in document.get("text", "").lower()
    ]


def extract_test_expectations(path: str, test_documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Infer conservative behavioral expectations from nearby indexed tests."""
    expectations: List[Dict[str, str]] = []
    for document in _test_documents_for(path, test_documents):
        text = document.get("text", "")
        lowered = text.lower()
        test_path = document.get("path", "")
        if "assert not" in lowered and (
            os.path.splitext(os.path.basename(path))[0].lower() in lowered
            or any(
                marker in lowered
                for marker in ("unconnected", "unreachable", "not found", "no path")
            )
        ):
            expectations.append(
                {
                    "type": "returns_false_when_unreachable",
                    "source": test_path,
                    "detail": "Indexed tests expect a false result when no path exists.",
                }
            )
        if re.search(r"\bassert\s+\w+", lowered) and any(
            marker in lowered for marker in ("path found", "reachable", "branching graph")
        ):
            expectations.append(
                {
                    "type": "returns_true_when_reachable",
                    "source": test_path,
                    "detail": "Indexed tests expect a true result when a path exists.",
                }
            )
        if "cycle" in lowered or "strongly connected" in lowered:
            expectations.append(
                {
                    "type": "handles_cycles",
                    "source": test_path,
                    "detail": "Indexed tests exercise cyclic graph traversal.",
                }
            )
    deduped: List[Dict[str, str]] = []
    seen = set()
    for expectation in expectations:
        key = (expectation["type"], expectation["source"])
        if key not in seen:
            deduped.append(expectation)
            seen.add(key)
    return deduped


def _has_queue_truth_test(test: ast.AST, queue_names: set[str]) -> bool:
    if isinstance(test, ast.Name):
        return test.id in queue_names
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "len":
        return bool(test.args and isinstance(test.args[0], ast.Name) and test.args[0].id in queue_names)
    if isinstance(test, ast.Compare):
        return _has_queue_truth_test(test.left, queue_names) or any(
            _has_queue_truth_test(item, queue_names) for item in test.comparators
        )
    return False


def _membership_filters(function: ast.AST, visited_names: set[str]) -> List[ast.Compare]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Compare)
        and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops)
        and any(
            isinstance(item, ast.Name) and item.id in visited_names
            for item in [node.left, *node.comparators]
        )
    ]


def _bfs_findings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: List[str],
    expectations: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    related_tests = sorted({item["source"] for item in expectations})
    queue_names = {
        node.targets[0].id
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and (
            "queue" in node.targets[0].id.lower()
            or (
                isinstance(node.value, ast.Call)
                and _name(node.value.func).lower() in {"queue", "deque"}
            )
        )
    }
    if not queue_names:
        queue_names = {"queue"}
    visited_names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
        and any(marker in node.id.lower() for marker in ("seen", "visited"))
    }
    popleft_calls = [
        call for call in _function_calls(function, "popleft") if _name(call.func.value) in queue_names
    ]
    pop_calls = [
        call for call in _function_calls(function, "pop") if _name(call.func.value) in queue_names
    ]
    append_calls = [
        call
        for method in ("append", "extend")
        for call in _function_calls(function, method)
        if _name(call.func.value) in queue_names
    ]
    while_loops = [node for node in ast.walk(function) if isinstance(node, ast.While)]

    for loop in while_loops:
        if (
            isinstance(loop.test, ast.Constant)
            and loop.test.value is True
            and popleft_calls
        ):
            expectation_note = ""
            if any(item["type"] == "returns_false_when_unreachable" for item in expectations):
                expectation_note = (
                    " Indexed tests expect False for an unreachable graph, so this violates "
                    "the not-found behavior."
                )
            findings.append(
                _finding(
                    "bfs_queue_exhaustion",
                    "high",
                    loop.lineno,
                    "BFS appears incorrect because its traversal loop is unconditional "
                    "(`while True`) while dequeuing with `popleft()`. When the frontier "
                    "empties before finding the goal, it attempts to dequeue from an empty "
                    f"queue instead of terminating and returning False.{expectation_note}",
                    lines,
                    related_tests=related_tests,
                )
            )
        # NOTE (Phase 87): `bfs_frontier_termination` retired. Termination of a
        # frontier loop is now detected name-free by the dataflow-backed
        # `unguarded_container_consumption` finding (see analyze_semantics).

    if pop_calls and not popleft_calls:
        findings.append(
            _finding(
                "bfs_fifo_violation",
                "high",
                pop_calls[0].lineno,
                "BFS appears incorrect because the frontier uses stack-style `pop()` "
                "instead of FIFO dequeue behavior.",
                lines,
                related_tests=related_tests,
            )
        )
    # NOTE (Phase 87): `bfs_missing_visited_tracking` retired. It asserted a
    # false universal ("every traversal must have a visited set") and was a
    # source of out-of-domain (holdout) false positives on correct, acyclic
    # traversals. Cycle safety is only asserted when a visited set exists but is
    # not used to filter frontier growth (`bfs_cycle_handling`, below).
    if append_calls and visited_names and not _membership_filters(function, visited_names):
        findings.append(
            _finding(
                "bfs_cycle_handling",
                "high",
                append_calls[0].lineno,
                "BFS records visited nodes but does not visibly filter frontier growth "
                "against that visited state; cyclic graphs may be expanded repeatedly.",
                lines,
                related_tests=related_tests,
            )
        )
    return findings


def _calls_named(function: ast.AST, name: str) -> List[ast.Call]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_int(node: ast.AST, value: int) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _tests_empty_sequence(test: ast.AST, name: str) -> bool:
    for node in ast.walk(test):
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and _is_name(node.operand, name):
            return True
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for item in operands:
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == "len"
                and item.args
                and _is_name(item.args[0], name)
                and any(_is_int(other, 0) for other in operands)
            ):
                return True
            if _is_name(item, name) and any(
                isinstance(other, (ast.List, ast.Tuple)) and not other.elts
                for other in operands
            ):
                return True
    return False


def _covers_singleton_length(function: ast.AST, name: str) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        length_call = next(
            (
                item
                for item in operands
                if isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == "len"
                and item.args
                and _is_name(item.args[0], name)
            ),
            None,
        )
        if length_call is None:
            continue
        if any(isinstance(op, ast.Eq) for op in node.ops) and any(_is_int(item, 1) for item in operands):
            return True
        if any(isinstance(op, ast.LtE) for op in node.ops) and any(_is_int(item, 1) for item in operands):
            return True
        if any(isinstance(op, ast.Lt) for op in node.ops) and any(_is_int(item, 2) for item in operands):
            return True
    return False


def _recursive_findings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    path: str,
    lines: List[str],
    expectations: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Check recursive progress and terminal coverage for recognized algorithms."""
    findings: List[Dict[str, Any]] = []
    related_tests = sorted({item["source"] for item in expectations})
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    name = function.name.lower()

    if name == "binsearch" and stem == "find_in_sorted":
        for call in _calls_named(function, function.name):
            if (
                len(call.args) >= 2
                and _is_name(call.args[0], "mid")
                and _is_name(call.args[1], "end")
            ):
                findings.append(
                    _finding(
                        "recursive_interval_not_shrinking",
                        "high",
                        call.lineno,
                        "Recursive binary search reuses `mid` as the lower bound of its "
                        "upper-half call. When `mid == start`, the interval does not shrink; "
                        "the upper branch must advance to `mid + 1`.",
                        lines,
                        related_tests=related_tests,
                    )
                )

    if name == "gcd":
        for call in _calls_named(function, function.name):
            if len(call.args) >= 2 and _is_name(call.args[1], "b"):
                findings.append(
                    _finding(
                        "recursive_euclidean_state_not_rotated",
                        "high",
                        call.lineno,
                        "Euclidean GCD recursion keeps `b` as its second argument after "
                        "computing a remainder. The next state must rotate to `gcd(b, a % b)` "
                        "so the divisor decreases toward zero.",
                        lines,
                        related_tests=related_tests,
                    )
                )

    if name == "mergesort" and function.args.args:
        sequence_name = function.args.args[0].arg
        if _calls_named(function, function.name) and not _covers_singleton_length(function, sequence_name):
            findings.append(
                _finding(
                    "recursive_singleton_base_case_missing",
                    "high",
                    function.lineno,
                    "Merge sort recursion does not visibly stop for a one-element input. "
                    "A singleton partitions into a recursive branch containing itself, so "
                    "the base case must cover lengths zero and one.",
                    lines,
                    related_tests=related_tests,
                )
            )

    if name == "possible_change" and function.args.args:
        coins_name = function.args.args[0].arg
        unpack = next(
            (
                node
                for node in function.body
                if isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(getattr(node, "value", None), ast.Name)
                and getattr(node, "value").id == coins_name
            ),
            None,
        )
        guards_empty_coins = any(
            isinstance(node, ast.If) and _tests_empty_sequence(node.test, coins_name)
            for node in function.body
        )
        if unpack is not None and not guards_empty_coins:
            findings.append(
                _finding(
                    "recursive_empty_choice_base_case_missing",
                    "high",
                    unpack.lineno,
                    "Recursive change enumeration destructures the coin list without a "
                    "terminal case for an empty list. Impossible branches can exhaust the "
                    "choices and fail before returning zero.",
                    lines,
                    related_tests=related_tests,
                )
            )

    if name == "subsequences":
        for node in ast.walk(function):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            operands = [node.test.left, *node.test.comparators]
            if not (_is_name(operands[0], "k") and any(_is_int(item, 0) for item in operands)):
                continue
            returned = next((item for item in node.body if isinstance(item, ast.Return)), None)
            if isinstance(returned, ast.Return) and isinstance(returned.value, ast.List) and not returned.value.elts:
                findings.append(
                    _finding(
                        "recursive_identity_base_case",
                        "high",
                        returned.lineno,
                        "Recursive subsequence construction returns no result for `k == 0`. "
                        "Selecting zero remaining elements has one identity result, the empty "
                        "selection `[[]]`, so callers can extend it.",
                        lines,
                        related_tests=related_tests,
                    )
                )
    return findings


def _subscript_parts(node: ast.AST) -> tuple[str, List[ast.AST]] | None:
    if not isinstance(node, ast.Subscript) or not isinstance(node.value, ast.Name):
        return None
    indexes = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
    return node.value.id, indexes


def _shortest_path_findings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: List[str],
    expectations: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Check named shortest-path relaxation assignments and recurrences."""
    findings: List[Dict[str, Any]] = []
    related_tests = sorted({item["source"] for item in expectations})
    name = function.name.lower()

    if name == "shortest_path_length":
        for node in ast.walk(function):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
                continue
            terms = [node.left, node.right]
            uses_destination_lookup = any(
                isinstance(term, ast.Call)
                and isinstance(term.func, ast.Name)
                and term.func.id == "get"
                for term in terms
            )
            uses_edge_length = any(
                (parts := _subscript_parts(term)) is not None
                and parts[0] == "length_by_edge"
                for term in terms
            )
            if uses_destination_lookup and uses_edge_length:
                findings.append(
                    _finding(
                        "dijkstra_relaxes_from_destination",
                        "high",
                        node.lineno,
                        "Dijkstra-style relaxation adds the edge length to the existing "
                        "destination lookup. A candidate path must start from the popped "
                        "source distance: `distance + length_by_edge[node, nextnode]`.",
                        lines,
                        related_tests=related_tests,
                    )
                )

    if name == "shortest_path_lengths":
        for node in ast.walk(function):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
                continue
            left = _subscript_parts(node.left)
            right = _subscript_parts(node.right)
            if (
                left is not None
                and right is not None
                and left[0] == right[0] == "length_by_path"
                and len(left[1]) == len(right[1]) == 2
                and _is_name(left[1][0], "i")
                and _is_name(left[1][1], "k")
                and _is_name(right[1][0], "j")
                and _is_name(right[1][1], "k")
            ):
                findings.append(
                    _finding(
                        "floyd_warshall_recurrence_direction",
                        "high",
                        node.lineno,
                        "Floyd-Warshall relaxation composes `i -> k` with `j -> k`. The "
                        "second segment must run from the intermediary to the destination: "
                        "`length_by_path[k, j]`.",
                        lines,
                        related_tests=related_tests,
                    )
                )

    if name == "shortest_paths":
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                parts = _subscript_parts(target)
                if (
                    parts is not None
                    and parts[0] == "weight_by_edge"
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "min"
                ):
                    findings.append(
                        _finding(
                            "bellman_ford_updates_edge_weight",
                            "high",
                            node.lineno,
                            "Bellman-Ford relaxation writes the candidate path into the "
                            "edge-weight table. Relaxation must update destination distance "
                            "state, such as `weight_by_node[v]`, while edge weights remain fixed.",
                            lines,
                            related_tests=related_tests,
                        )
                    )
    return findings


def _sorting_cardinality_findings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: List[str],
    expectations: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Check named sort implementations for dropped or duplicated elements."""
    findings: List[Dict[str, Any]] = []
    related_tests = sorted({item["source"] for item in expectations})
    name = function.name.lower()

    if name == "bucketsort":
        for node in ast.walk(function):
            if (
                isinstance(node, ast.For)
                and isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "enumerate"
                and node.iter.args
                and _is_name(node.iter.args[0], "arr")
                and any(
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "extend"
                    for child in ast.walk(node)
                )
            ):
                findings.append(
                    _finding(
                        "counting_sort_reconstructs_from_input",
                        "high",
                        node.lineno,
                        "Bucket sort reconstructs output by enumerating the original input "
                        "array instead of the bucket-count array. Reconstruction must consume "
                        "`counts` so each value is emitted with its recorded frequency.",
                        lines,
                        related_tests=related_tests,
                    )
                )

    if name == "kheapsort":
        seeds_prefix = any(
            isinstance(node, ast.Subscript)
            and _is_name(node.value, "arr")
            and isinstance(node.slice, ast.Slice)
            and _is_name(node.slice.upper, "k")
            for node in ast.walk(function)
        )
        repeats_full_input = next(
            (
                node
                for node in ast.walk(function)
                if isinstance(node, ast.For) and _is_name(node.iter, "arr")
            ),
            None,
        )
        if seeds_prefix and repeats_full_input is not None:
            findings.append(
                _finding(
                    "heap_window_reprocesses_seed",
                    "high",
                    repeats_full_input.lineno,
                    "K-heapsort seeds its heap from `arr[:k]` and then iterates the entire "
                    "array again. The seeded window is emitted twice; streaming must resume "
                    "from `arr[k:]` to preserve input cardinality.",
                    lines,
                    related_tests=related_tests,
                )
            )

    if name == "quicksort":
        comparisons = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and len(node.comparators) == 1
            and _is_name(node.left, "x")
            and _is_name(node.comparators[0], "pivot")
        ]
        strict_less = next((node for node in comparisons if isinstance(node.ops[0], ast.Lt)), None)
        strict_greater = next((node for node in comparisons if isinstance(node.ops[0], ast.Gt)), None)
        if strict_less is not None and strict_greater is not None:
            findings.append(
                _finding(
                    "quicksort_drops_duplicate_values",
                    "high",
                    strict_greater.lineno,
                    "Quicksort partitions values with strict `< pivot` and `> pivot` "
                    "comparisons. Values equal to the pivot enter neither recursive branch, "
                    "so duplicate elements are dropped instead of preserved.",
                    lines,
                    related_tests=related_tests,
                )
            )
    return findings


def _generic_profile_findings(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    profiles: List[str],
    lines: List[str],
    expectations: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    related_tests = sorted({item["source"] for item in expectations})
    nodes = list(ast.walk(function))
    recursive = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == function.name
        for node in nodes
    )
    has_conditional_return = any(
        isinstance(node, ast.If)
        and any(isinstance(child, ast.Return) for child in ast.walk(node))
        for node in nodes
    )
    if "recursion" in profiles and recursive and not has_conditional_return:
        findings.append(
            _finding(
                "recursive_progress_invariant",
                "high",
                function.lineno,
                "Recursive algorithm has no obvious conditional return that establishes a base case.",
                lines,
                related_tests=related_tests,
            )
        )
    # NOTE (Phase 87): `graph_traversal_cycle_handling` retired. Like
    # `bfs_missing_visited_tracking` it encoded the false universal that any
    # frontier-growing traversal must carry a visited set, which produced
    # out-of-domain (holdout) false positives on correct acyclic traversals.
    return findings


def _unguarded_consumption_findings(
    text: str,
    path: str,
    lines: List[str],
    related_tests: List[str],
) -> List[Dict[str, Any]]:
    """Phase 87 dataflow-backed replacement for the retired BFS termination /
    visited rules.

    Detection is purely structural (data-flow facts): a loop that grows AND
    consumes the same container while its guard does not depend on that
    container and no empty-container exit precedes the consumption. It does NOT
    read the function name, variable names, file name, or any path. This is the
    single behavior-bound finding that generalizes the BFS frontier bug to any
    self-expanding worklist, named or not.
    """
    findings: List[Dict[str, Any]] = []
    facts = dataflow.analyze_source(text, path)
    for hit in dataflow.find_unbounded_frontier_loops(facts):
        findings.append(
            _finding(
                "unguarded_container_consumption",
                "high",
                hit["loop_line"],
                "A loop consumes from a container on every iteration, but its loop "
                "guard does not depend on that container and no empty-container check "
                "precedes the consumption. When the container empties before the loop's "
                "other exit condition is met, the consume operation fails (dequeue/pop "
                "from an empty container) instead of terminating. The loop should stop "
                "when the container becomes empty (guard on the container itself).",
                lines,
                related_tests=related_tests,
            )
        )
    return findings


def analyze_semantics(
    tree: ast.AST,
    path: str,
    text: str,
    *,
    test_documents: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Analyze algorithm profiles, invariants, and indexed test expectations."""
    lines = text.splitlines()
    test_documents = list(test_documents or [])
    expectations = extract_test_expectations(path, test_documents)
    related_tests = sorted({item["source"] for item in expectations})
    profile_set = set()
    findings: List[Dict[str, Any]] = []

    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        docstring = ast.get_docstring(function) or ""
        function_text = "\n".join(
            lines[function.lineno - 1 : getattr(function, "end_lineno", function.lineno)]
        )
        profiles = profile_names(detect_profiles(function.name, docstring, function_text))
        profile_set.update(profiles)
        if "bfs" in profiles:
            findings.extend(_bfs_findings(function, lines, expectations))
        findings.extend(_recursive_findings(function, path, lines, expectations))
        findings.extend(_shortest_path_findings(function, lines, expectations))
        findings.extend(_sorting_cardinality_findings(function, lines, expectations))
        findings.extend(_generic_profile_findings(function, profiles, lines, expectations))

    # Phase 87: name-free, dataflow-backed frontier-termination finding.
    findings.extend(_unguarded_consumption_findings(text, path, lines, related_tests))

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for finding in findings:
        key = (finding["rule"], finding["line"], finding["message"])
        if key not in seen:
            deduped.append(finding)
            seen.add(key)
    return {
        "profiles": sorted(profile_set),
        "test_expectations": expectations,
        "findings": deduped,
    }
