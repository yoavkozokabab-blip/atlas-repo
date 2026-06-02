"""Tests for the Phase 86 Data Flow Analysis fact layer.

These tests assert on *facts*, never on findings. The central claim under test:
the QuixBugs BFS bug is representable as a structural fact triple with no
function-name matching, and those facts are stable under renaming.
"""

from __future__ import annotations

import textwrap

from builder_core.bug_intelligence import dataflow


def _facts(src: str):
    return dataflow.analyze_source(textwrap.dedent(src))


def _only_fn(src: str):
    fns = _facts(src)["functions"]
    assert len(fns) == 1
    return fns[0]


def _first_loop(src: str):
    fn = _only_fn(src)
    assert fn["loops"], "expected at least one loop"
    return fn["loops"][0]


# ---------------------------------------------------------------------------
# 1. while True + popleft, no empty guard  -> the BFS bug shape
# ---------------------------------------------------------------------------
WHILE_TRUE_POPLEFT = """
    def search(start, goal):
        queue = []
        queue.append(start)
        while True:
            node = queue.popleft()
            if node == goal:
                return True
            queue.extend(start.successors)
        return False
"""


def test_while_true_popleft_is_unguarded_consumption():
    loop = _first_loop(WHILE_TRUE_POPLEFT)
    assert "queue" in loop["consumes"]
    assert loop["termination_depends_on_consumed_container"] is False
    assert loop["has_empty_guard_before_consume"] is False
    assert loop["unguarded_consumption"] is True


# ---------------------------------------------------------------------------
# 2. while queue + popleft  -> guarded by the container itself
# ---------------------------------------------------------------------------
WHILE_QUEUE_POPLEFT = """
    def search(start, goal):
        queue = []
        queue.append(start)
        while queue:
            node = queue.popleft()
            if node == goal:
                return True
            queue.extend(start.successors)
        return False
"""


def test_while_queue_popleft_depends_on_container():
    loop = _first_loop(WHILE_QUEUE_POPLEFT)
    assert "queue" in loop["consumes"]
    assert "queue" in loop["guard_vars"]
    assert loop["termination_depends_on_consumed_container"] is True
    assert loop["unguarded_consumption"] is False


# ---------------------------------------------------------------------------
# 3. while True + explicit empty exit before popleft  -> guarded in body
# ---------------------------------------------------------------------------
WHILE_TRUE_GUARDED = """
    def search(start, goal):
        queue = []
        queue.append(start)
        while True:
            if not queue:
                return False
            node = queue.popleft()
            if node == goal:
                return True
            queue.extend(start.successors)
"""


def test_while_true_with_empty_exit_is_guarded():
    loop = _first_loop(WHILE_TRUE_GUARDED)
    assert "queue" in loop["consumes"]
    assert loop["termination_depends_on_consumed_container"] is False
    assert loop["has_empty_guard_before_consume"] is True
    assert loop["unguarded_consumption"] is False


# ---------------------------------------------------------------------------
# 4. recursion with shrinking argument
# ---------------------------------------------------------------------------
def test_recursion_shrinking_argument():
    fn = _only_fn("""
        def fact(n):
            if n <= 1:
                return 1
            return n * fact(n - 1)
    """)
    rec = fn["recursion"]
    assert rec["is_recursive"] is True
    assert rec["shrinks_any_arg"] is True
    assert rec["has_base_case"] is True


# ---------------------------------------------------------------------------
# 5. recursion with non-shrinking argument
# ---------------------------------------------------------------------------
def test_recursion_non_shrinking_argument():
    fn = _only_fn("""
        def loop(n):
            return loop(n)
    """)
    rec = fn["recursion"]
    assert rec["is_recursive"] is True
    assert rec["shrinks_any_arg"] is False
    assert rec["calls"][0]["arg_changes"][0]["change"] == "same"
    assert rec["has_base_case"] is False


# ---------------------------------------------------------------------------
# 6. append / pop container mutation facts
# ---------------------------------------------------------------------------
def test_container_mutation_facts():
    fn = _only_fn("""
        def use():
            stack = []
            stack.append(1)
            stack.append(2)
            stack.pop()
            return stack
    """)
    containers = {c["name"]: c for c in fn["containers"]}
    assert "stack" in containers
    stack = containers["stack"]
    assert stack["grown"] is True
    assert stack["consumed"] is True
    assert stack["created_as"] == "list"
    ops = sorted(m["op"] for m in stack["mutations"])
    assert ops == ["append", "append", "pop"]
    # list.pop() with no arg is LIFO
    assert stack["consume_behavior"] == "lifo"


def test_fifo_vs_lifo_behavior():
    fn = _only_fn("""
        def use():
            q = []
            q.append(1)
            q.popleft()
            return q
    """)
    q = {c["name"]: c for c in fn["containers"]}["q"]
    assert q["consume_behavior"] == "fifo"


# ---------------------------------------------------------------------------
# 7. variable def-use facts
# ---------------------------------------------------------------------------
def test_variable_def_use_facts():
    fn = _only_fn("""
        def compute(a):
            b = a + 1
            c = b * 2
            return c
    """)
    du = fn["def_use"]
    # 'a' is a param (def at function line) and used on the 'b = a + 1' line
    assert du["a"]["defined"] is True
    assert du["a"]["used"] is True
    # 'b' defined then used
    assert du["b"]["defs"] and du["b"]["uses"]
    # 'c' defined then returned (used)
    assert du["c"]["defined"] is True and du["c"]["used"] is True
    assert "a" in fn["params"]


def test_unused_definition_visible_in_def_use():
    fn = _only_fn("""
        def f(x):
            y = x + 1
            return x
    """)
    du = fn["def_use"]
    # 'y' is defined but never used — a fact, not a finding
    assert du["y"]["defined"] is True
    assert du["y"]["used"] is False


# ---------------------------------------------------------------------------
# 8. Name-agnosticism / rename stability — the Phase 85 concern
# ---------------------------------------------------------------------------
NAMED_BFS = """
    def breadth_first_search(startnode, goalnode):
        queue = []
        queue.append(startnode)
        nodesseen = set()
        while True:
            node = queue.popleft()
            if node == goalnode:
                return True
            queue.extend(startnode.successors)
        return False
"""

RENAMED_BFS = """
    def f1(p0, p1):
        v0 = []
        v0.append(p0)
        v1 = set()
        while True:
            v2 = v0.popleft()
            if v2 == p1:
                return True
            v0.extend(p0.successors)
        return False
"""


def _structural_loop_signature(loop):
    """Only the name-independent structural booleans."""
    return (
        bool(loop["consumes"]),
        loop["termination_depends_on_consumed_container"],
        loop["has_empty_guard_before_consume"],
        loop["unguarded_consumption"],
        tuple(loop["consume_order"]),
    )


def test_bug_facts_are_stable_under_renaming():
    named = _first_loop(NAMED_BFS)
    renamed = _first_loop(RENAMED_BFS)
    assert _structural_loop_signature(named) == _structural_loop_signature(renamed)
    # and the bug shape is detected in both, by structure alone
    assert named["unguarded_consumption"] is True
    assert renamed["unguarded_consumption"] is True


def test_fact_pattern_query_detects_bug_without_names():
    facts = _facts(RENAMED_BFS)  # function called 'f1', vars v0/v1/v2
    hits = dataflow.find_unguarded_consumption_loops(facts)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["function"] == "f1"  # query never matched on the name
    assert "v0" in hit["consumed_containers"]


def test_correct_bfs_not_flagged_by_fact_pattern():
    facts = _facts(WHILE_QUEUE_POPLEFT)
    assert dataflow.find_unguarded_consumption_loops(facts) == []


# ---------------------------------------------------------------------------
# 9. loop guard variable extraction
# ---------------------------------------------------------------------------
def test_loop_guard_vars_extracted():
    loop = _first_loop("""
        def f(items):
            i = 0
            while i < len(items):
                i = i + 1
            return i
    """)
    assert set(loop["guard_vars"]) >= {"i", "items"}


# ---------------------------------------------------------------------------
# 10. parse errors degrade gracefully
# ---------------------------------------------------------------------------
def test_syntax_error_returns_empty_functions():
    facts = dataflow.analyze_source("def broken(:\n  pass\n")
    assert facts["parse_error"]
    assert facts["functions"] == []
