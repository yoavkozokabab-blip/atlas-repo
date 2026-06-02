"""Phase 87 regression tests: dataflow-backed rule rewire.

Verifies, on the SEMANTIC path that drives the benchmarks, that:
- the buggy BFS frontier bug flags (via the name-free rule),
- the corrected BFS does not flag (the Phase 84 holdout FP source is gone),
- renaming the function/variables does not change either verdict,
- the retired name-bound rules no longer fire.
"""

from __future__ import annotations

import ast
import textwrap

from builder_core import semantic_reasoning as sr

RETIRED_RULES = {
    "bfs_frontier_termination",
    "bfs_missing_visited_tracking",
    "graph_traversal_cycle_handling",
}

NEW_RULE = "unguarded_container_consumption"


def _rules(src: str, path: str = "breadth_first_search.py") -> set:
    src = textwrap.dedent(src)
    result = sr.analyze_semantics(ast.parse(src), path, src)
    return {f["rule"] for f in result["findings"]}


BUGGY_BFS = """
    from collections import deque as Queue
    def breadth_first_search(startnode, goalnode):
        queue = Queue()
        queue.append(startnode)
        nodesseen = set()
        nodesseen.add(startnode)
        while True:
            node = queue.popleft()
            if node is goalnode:
                return True
            else:
                queue.extend(n for n in node.successors if n not in nodesseen)
                nodesseen.update(node.successors)
        return False
"""

CORRECT_BFS = BUGGY_BFS.replace("while True:", "while queue:")

RENAMED_BUGGY_BFS = """
    from collections import deque as Q
    def f1(p0, p1):
        v0 = Q()
        v0.append(p0)
        v1 = set()
        v1.add(p0)
        while True:
            v2 = v0.popleft()
            if v2 is p1:
                return True
            else:
                v0.extend(n for n in v2.succ if n not in v1)
                v1.update(v2.succ)
        return False
"""

RENAMED_CORRECT_BFS = RENAMED_BUGGY_BFS.replace("while True:", "while v0:")


# ---------------------------------------------------------------------------
# Required regression cases
# ---------------------------------------------------------------------------
def test_buggy_bfs_flags():
    assert NEW_RULE in _rules(BUGGY_BFS)


def test_correct_bfs_does_not_flag():
    rules = _rules(CORRECT_BFS)
    assert NEW_RULE not in rules
    # corrected BFS produces no semantic finding at all -> no false positive
    assert rules == set()


def test_renamed_buggy_bfs_still_flags():
    # The function is 'f1' and all vars are renamed; only a name-free rule can fire.
    rules = _rules(RENAMED_BUGGY_BFS, path="f1.py")
    assert NEW_RULE in rules


def test_renamed_correct_bfs_still_does_not_flag():
    assert _rules(RENAMED_CORRECT_BFS, path="f1.py") == set()


# ---------------------------------------------------------------------------
# Retirement assertions
# ---------------------------------------------------------------------------
def test_retired_rules_never_fire():
    seen = (
        _rules(BUGGY_BFS)
        | _rules(CORRECT_BFS)
        | _rules(RENAMED_BUGGY_BFS, path="f1.py")
        | _rules(RENAMED_CORRECT_BFS, path="f1.py")
    )
    assert not (RETIRED_RULES & seen)


def test_new_rule_is_name_free_for_non_bfs_named_worklist():
    # A self-expanding worklist NOT named like any algorithm must still flag.
    src = """
        def process(items):
            work = list(items)
            results = []
            while True:
                item = work.pop()
                results.append(item)
                work.extend(item.children)
    """
    assert NEW_RULE in _rules(src, path="process.py")


def test_bounded_worklist_not_flagged():
    # Guarded by the container itself -> not a bug -> no finding.
    src = """
        def process(items):
            work = list(items)
            results = []
            while work:
                item = work.pop()
                results.append(item)
                work.extend(item.children)
            return results
    """
    assert NEW_RULE not in _rules(src, path="process.py")
