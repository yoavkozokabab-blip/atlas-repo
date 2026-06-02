"""Tests for the Bug Intelligence subsystem (Phase 83).

Each synthetic example embeds one canonical logic bug. Tests assert that the
deterministic analyzer flags the expected rule with line-anchored evidence.
All work happens on in-memory source or pytest tmp_path; no target repo is
modified and no network/LLM is used.
"""

from __future__ import annotations

import os
import textwrap

import pytest

from builder_core.bug_intelligence import analyzer, ranking
from builder_core.bug_intelligence.analyzer import analyze_source


def _rules(report) -> set:
    return {f.rule for f in report.findings}


def _analyze(src: str, name: str = "sample.py"):
    return analyze_source(name, textwrap.dedent(src), test_awareness=False)


# ---------------------------------------------------------------------------
# Recursion bug
# ---------------------------------------------------------------------------
def test_recursion_without_base_case():
    report = _analyze(
        """
        def countdown(n):
            print(n)
            return countdown(n - 1)
        """,
        "countdown.py",
    )
    assert "recursion_no_termination" in _rules(report)
    f = next(f for f in report.findings if f.rule == "recursion_no_termination")
    assert f.function == "countdown"
    assert "base case" in f.title.lower()
    assert "recursion" in f.message.lower()


def test_recursion_with_base_case_is_not_flagged():
    report = _analyze(
        """
        def factorial(n):
            if n <= 1:
                return 1
            return n * factorial(n - 1)
        """,
        "factorial.py",
    )
    assert "recursion_no_termination" not in _rules(report)


# ---------------------------------------------------------------------------
# Off-by-one
# ---------------------------------------------------------------------------
def test_off_by_one_range_len_plus_one():
    report = _analyze(
        """
        def total(seq):
            s = 0
            for i in range(len(seq) + 1):
                s += seq[i]
            return s
        """,
        "total.py",
    )
    assert "off_by_one" in _rules(report)
    f = next(f for f in report.findings if f.rule == "off_by_one")
    assert f.line >= 1 and f.evidence


def test_off_by_one_inclusive_len_comparison():
    report = _analyze(
        """
        def at_boundary(seq, i):
            if i <= len(seq):
                return seq[i]
            return None
        """,
        "boundary.py",
    )
    assert "off_by_one" in _rules(report)


# ---------------------------------------------------------------------------
# Mutation during iteration
# ---------------------------------------------------------------------------
def test_mutation_during_iteration():
    report = _analyze(
        """
        def prune(items):
            for x in items:
                if x < 0:
                    items.remove(x)
            return items
        """,
        "prune.py",
    )
    assert "mutation_while_iterating" in _rules(report)
    f = next(f for f in report.findings if f.rule == "mutation_while_iterating")
    assert "items" in f.message


# ---------------------------------------------------------------------------
# Inconsistent return types
# ---------------------------------------------------------------------------
def test_inconsistent_return_types():
    report = _analyze(
        """
        def lookup(d, k):
            if k in d:
                return d[k]
            return False
        """,
        "lookup.py",
    )
    assert "inconsistent_return" in _rules(report)


# ---------------------------------------------------------------------------
# Unreachable code
# ---------------------------------------------------------------------------
def test_unreachable_code_after_return():
    report = _analyze(
        """
        def f(x):
            return x
            x += 1
        """,
        "unreach.py",
    )
    assert "unreachable_code" in _rules(report)
    f = next(f for f in report.findings if f.rule == "unreachable_code")
    assert f.line == 4


# ---------------------------------------------------------------------------
# Duplicated branches / impossible condition / exception swallowing
# ---------------------------------------------------------------------------
def test_duplicated_branches():
    report = _analyze(
        """
        def pick(flag, a):
            if flag:
                return a + 1
            else:
                return a + 1
        """,
        "pick.py",
    )
    assert "duplicated_branches" in _rules(report)


def test_impossible_condition():
    report = _analyze(
        """
        def g(x):
            if x > 5 and x < 3:
                return x
            return 0
        """,
        "imposs.py",
    )
    assert "impossible_condition" in _rules(report)


def test_exception_swallowing():
    report = _analyze(
        """
        def risky():
            try:
                do_thing()
            except Exception:
                pass
        """,
        "risky.py",
    )
    assert "exception_swallowed" in _rules(report)


def test_shadowed_builtin():
    report = _analyze(
        """
        def h(values):
            list = []
            for v in values:
                list.append(v)
            return list
        """,
        "shadow.py",
    )
    assert "shadowed_name" in _rules(report)


# ---------------------------------------------------------------------------
# Algorithm / name mismatch — the headline capability
# ---------------------------------------------------------------------------
def test_bfs_unguarded_consumption_while_true():
    # Phase 87: the BFS frontier bug is now caught name-free, by the
    # dataflow-backed unguarded_container_consumption rule (not algorithm_mismatch).
    report = _analyze(
        """
        def breadth_first_search(start, goal):
            queue = [start]
            seen = set()
            while True:
                node = queue.pop()
                if node is goal:
                    return True
                for nxt in node.successors:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
        """,
        "breadth_first_search.py",
    )
    assert "unguarded_container_consumption" in _rules(report)


def test_bfs_while_true_no_empty_guard():
    # The classic QuixBugs BFS bug: `while True` instead of `while queue`
    report = _analyze(
        """
        from collections import deque
        def breadth_first_search(start, goal):
            queue = deque()
            queue.append(start)
            seen = set([start])
            while True:
                node = queue.popleft()
                if node is goal:
                    return True
                for nxt in node.successors:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
        """,
        "breadth_first_search.py",
    )
    assert "unguarded_container_consumption" in _rules(report)
    f = next(f for f in report.findings if f.rule == "unguarded_container_consumption")
    assert "empty" in f.message.lower() or "consum" in f.message.lower()


def test_correct_bfs_is_not_flagged():
    # Correct BFS (while queue:) must not be flagged by the new rule, and the
    # retired name-bound BFS algorithm_mismatch must be gone too.
    report = _analyze(
        """
        from collections import deque
        def breadth_first_search(start, goal):
            queue = deque([start])
            seen = {start}
            while queue:
                node = queue.popleft()
                if node == goal:
                    return True
                for nxt in node.successors:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
            return False
        """,
        "breadth_first_search.py",
    )
    assert "unguarded_container_consumption" not in _rules(report)
    assert "algorithm_mismatch" not in _rules(report)


# ---------------------------------------------------------------------------
# Repository scan + ranking
# ---------------------------------------------------------------------------
def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))


@pytest.fixture
def buggy_repo(tmp_path):
    root = tmp_path / "repo"
    _write(str(root / "graph_search.py"), """
        def breadth_first_search(start, goal):
            queue = [start]
            while True:
                node = queue.pop()
                if node is goal:
                    return True
                for n in node.successors:
                    queue.append(n)
            return False
    """)
    _write(str(root / "math_utils.py"), """
        def total(seq):
            s = 0
            for i in range(len(seq) + 1):
                s += seq[i]
            return s
    """)
    _write(str(root / "clean.py"), """
        def add(a, b):
            return a + b
    """)
    return str(root)


def test_bug_scan_ranks_files(buggy_repo):
    reports = analyzer.analyze_repository(buggy_repo)
    ranked = ranking.rank_reports(reports)
    ranked_paths = [r.rel_path for r in ranked]
    assert "graph_search.py" in ranked_paths
    assert "math_utils.py" in ranked_paths
    # the clean file should not be flagged
    assert "clean.py" not in ranked_paths
    # every ranked file carries at least one finding
    assert all(r.findings for r in ranked)


def test_ranking_is_score_ordered(buggy_repo):
    reports = analyzer.analyze_repository(buggy_repo)
    ranked = ranking.rank_reports(reports)
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Test awareness
# ---------------------------------------------------------------------------
def test_untested_module_flagged(tmp_path):
    root = tmp_path / "repo"
    _write(str(root / "src" / "widget.py"), """
        def widget_area(w, h):
            return w * h
    """)
    # a test file that does NOT mention widget
    _write(str(root / "tests" / "test_other.py"), """
        def test_nothing():
            assert True
    """)
    reports = analyzer.analyze_repository(root.as_posix())
    widget = next(r for r in reports if r.rel_path.endswith("widget.py"))
    assert "untested_module" in {f.rule for f in widget.findings}


# ---------------------------------------------------------------------------
# Syntax errors are reported, not crashed on
# ---------------------------------------------------------------------------
def test_syntax_error_is_a_finding():
    report = _analyze("def broken(:\n    pass\n", "broken.py")
    assert report.parse_error
    assert any(f.rule == "syntax_error" for f in report.findings)


# ---------------------------------------------------------------------------
# CLI end-to-end (in-process)
# ---------------------------------------------------------------------------
def test_cli_analyze_file(buggy_repo, capsys):
    from builder_core import cli

    rc = cli.main(["analyze-file", "--project", buggy_repo, "graph_search.py"])
    assert rc == 0
    out = capsys.readouterr().out
    # unified engine output sections
    assert "SUMMARY" in out
    assert "FINDINGS" in out
    assert "EVIDENCE" in out
    assert "SOURCES" in out
    assert "NEXT VERIFICATION STEPS" in out
    assert "unguarded_container_consumption" in out or "container" in out.lower()


def test_cli_bug_scan(buggy_repo, capsys):
    from builder_core import cli

    rc = cli.main(["bug-scan", "--project", buggy_repo, "--top", "5"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "graph_search.py" in out


def test_cli_analyze_missing_file(buggy_repo):
    from builder_core import cli

    rc = cli.main(["analyze-file", "--project", buggy_repo, "does_not_exist.py"])
    assert rc == 2


def test_cli_benchmark_without_dataset(tmp_path, capsys):
    from builder_core import cli

    rc = cli.main(["benchmark-quixbugs", "--project", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "QUIXBUGS BENCHMARK" in out
