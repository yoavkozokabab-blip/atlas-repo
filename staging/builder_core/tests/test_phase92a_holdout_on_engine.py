"""Phase 92A tests: holdout validation migrated onto the unified engine.

No new detectors are exercised. These tests pin the engine-based holdout
evaluator, the grounded-kind verdict (pattern-only findings excluded; security
excluded from the algorithm-bug verdict), corpus immutability, and that the
QuixBugs engine path is unchanged.
"""

from __future__ import annotations

import hashlib
import os
import textwrap

import pytest

from builder_core.bug_intelligence import engine, engine_benchmark
from builder_core.bug_intelligence.finding import (
    Finding, LOGIC_BUG, SECURITY_RISK,
)


# ---------------------------------------------------------------------------
# Engine holdout evaluator runs and is 0 FP
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not (engine_benchmark._PAIRS_ROOT.is_dir()),
    reason="holdout corpus not present",
)
def test_holdout_engine_runs_and_zero_fp():
    report = engine_benchmark.evaluate_holdout_engine()
    assert report["available"] is True
    assert report["engine"] == "unified"
    assert report["cases_analyzed"] >= 1
    assert report["false_positives"] == 0          # acceptance gate
    assert report["true_positives"] >= 2            # parity with legacy holdout


def test_holdout_engine_missing_corpus_is_graceful(tmp_path):
    report = engine_benchmark.evaluate_holdout_engine(pairs_root=tmp_path / "nope")
    assert report["available"] is False
    out = engine_benchmark.format_holdout_report(report)
    assert "EXTERNAL HOLDOUT BENCHMARK" in out
    assert "engine=unified" in out


# ---------------------------------------------------------------------------
# Verdict uses grounded kinds only
# ---------------------------------------------------------------------------
def _result_with(*findings):
    class _R:
        pass
    r = _R()
    r.findings = list(findings)
    return r


def _f(kind, category=LOGIC_BUG, rule="x"):
    return Finding(category=category, kind=kind, severity="high", confidence="high",
                   file="x.py", line=1, title="t", explanation="e",
                   why_might_be_wrong="w", next_verification_step="n", rule=rule)


def test_pattern_only_finding_does_not_count():
    r = _result_with(_f("pattern", rule="inconsistent_return"))
    assert engine_benchmark.grounded_findings(r) == []


def test_security_kind_excluded_from_benchmark_verdict():
    # security is grounded but out of band for the algorithm-bug verdict
    r = _result_with(_f("security", category=SECURITY_RISK, rule="path_traversal"))
    assert engine_benchmark.grounded_findings(r) == []


def test_grounded_kinds_count():
    for kind in ("semantic", "data_flow", "value_flow"):
        r = _result_with(_f(kind, rule=f"r_{kind}"))
        assert len(engine_benchmark.grounded_findings(r)) == 1, kind


def test_naive_decision_includes_pattern():
    r = _result_with(_f("pattern", rule="inconsistent_return"))
    assert len(engine_benchmark.grounded_findings(r, grounded=False)) == 1


# ---------------------------------------------------------------------------
# Holdout corpus is not modified
# ---------------------------------------------------------------------------
def _snapshot(root) -> dict:
    snap = {}
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as fh:
                snap[os.path.relpath(p, root)] = hashlib.sha1(fh.read()).hexdigest()
    return snap


@pytest.mark.skipif(
    not (engine_benchmark._PAIRS_ROOT.is_dir()),
    reason="holdout corpus not present",
)
def test_holdout_corpus_not_modified():
    root = str(engine_benchmark._PAIRS_ROOT)
    before = _snapshot(root)
    engine_benchmark.evaluate_holdout_engine()
    after = _snapshot(root)
    assert before == after


# ---------------------------------------------------------------------------
# QuixBugs engine path remains unchanged (12 TP / 0 FP)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.path.isdir(r"C:\Repos\QuixBugs"),
    reason="QuixBugs dataset not present",
)
def test_quixbugs_engine_path_unchanged():
    report = engine_benchmark.evaluate_quixbugs_engine(r"C:\Repos\QuixBugs")
    assert report["true_positives"] == 12
    assert report["false_positives"] == 0
    assert report["precision"] == 1.0


# ---------------------------------------------------------------------------
# Engine holdout pairs run through the unified engine (synthetic, no corpus dep)
# ---------------------------------------------------------------------------
def test_engine_flags_synthetic_bfs_pair_via_grounded():
    buggy = textwrap.dedent('''
        from collections import deque as Queue
        def breadth_first_search(start, goal):
            """Breadth-First Search"""
            queue = Queue()
            queue.append(start)
            seen = set()
            while True:
                node = queue.popleft()
                if node is goal:
                    return True
                queue.extend(n for n in node.successors if n not in seen)
            return False
    ''')
    fixed = buggy.replace("while True:", "while queue:")
    b = engine_benchmark.grounded_findings(engine.analyze_source(buggy, "buggy.py"))
    f = engine_benchmark.grounded_findings(engine.analyze_source(fixed, "fixed.py"))
    assert b, "buggy BFS should yield a grounded finding"
    assert f == [], "fixed BFS should yield no grounded finding"
