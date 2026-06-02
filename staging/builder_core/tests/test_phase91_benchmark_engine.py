"""Phase 91 tests: benchmark-on-engine migration.

Covers engine selection / dispatch, that the engine benchmark does not modify
the target repo, and that duplicate findings (same rule reported by two detector
sources) do not inflate results.
"""

from __future__ import annotations

import hashlib
import os
import textwrap

import pytest

from builder_core.bug_intelligence import engine, engine_benchmark


# A buggy/correct BFS pair: while True (frontier never checks emptiness) vs while queue.
BUGGY_BFS = textwrap.dedent('''
    from collections import deque as Queue
    def breadth_first_search(startnode, goalnode):
        """Breadth-First Search"""
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
''')
CORRECT_BFS = BUGGY_BFS.replace("while True:", "while queue:")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


@pytest.fixture
def mini_quixbugs(tmp_path):
    root = tmp_path / "MiniQuixBugs"
    _write(str(root / "python_programs" / "breadth_first_search.py"), BUGGY_BFS)
    _write(str(root / "correct_python_programs" / "breadth_first_search.py"), CORRECT_BFS)
    # a support file that must be excluded from pairing
    _write(str(root / "python_programs" / "node.py"), "class Node: pass\n")
    _write(str(root / "correct_python_programs" / "node.py"), "class Node: pass\n")
    return str(root)


# ---------------------------------------------------------------------------
# Engine benchmark evaluation
# ---------------------------------------------------------------------------
def test_engine_benchmark_flags_buggy_not_correct(mini_quixbugs):
    report = engine_benchmark.evaluate_quixbugs_engine(mini_quixbugs)
    assert report["available"] is True
    assert report["engine"] == "unified"
    assert report["buggy_files_analyzed"] == 1
    assert report["correct_files_analyzed"] == 1
    assert report["true_positives"] == 1
    assert report["false_positives"] == 0
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert "node.py" in report["excluded_pairs"]


def test_engine_benchmark_handles_missing_dataset(tmp_path):
    report = engine_benchmark.evaluate_quixbugs_engine(str(tmp_path))
    assert report["available"] is False
    out = engine_benchmark.format_report(report)
    assert "QUIXBUGS BENCHMARK" in out
    assert "engine=unified" in out


def test_grounded_decision_excludes_pattern_noise():
    # A correct function that trips a pattern-kind heuristic (inconsistent return)
    # must NOT be counted by the grounded verdict.
    res = engine.analyze_source(textwrap.dedent("""
        def lookup(d, k):
            if k in d:
                return d[k]
            return False
    """), "lookup.py")
    grounded = engine_benchmark.grounded_findings(res, grounded=True)
    naive = engine_benchmark.grounded_findings(res, grounded=False)
    assert all(f.kind != "pattern" for f in grounded)
    # the pattern heuristic exists (naive sees it) but is excluded from the verdict
    assert any(f.rule == "inconsistent_return" for f in naive)
    assert not any(f.rule == "inconsistent_return" for f in grounded)


# ---------------------------------------------------------------------------
# No duplicate findings inflate results
# ---------------------------------------------------------------------------
def test_duplicate_rule_from_two_sources_counts_once():
    # unguarded_container_consumption is emitted by BOTH the data-flow detector
    # and the semantic layer; the engine must dedupe it to a single finding.
    res = engine.analyze_source(BUGGY_BFS, "breadth_first_search.py")
    ucc = [f for f in res.findings if f.rule == "unguarded_container_consumption"]
    assert len(ucc) == 1, f"expected 1 deduped finding, got {len(ucc)}"


# ---------------------------------------------------------------------------
# No target repo modification
# ---------------------------------------------------------------------------
def _snapshot(root: str):
    snap = {}
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as fh:
                snap[os.path.relpath(p, root)] = hashlib.sha1(fh.read()).hexdigest()
    return snap


def test_engine_benchmark_does_not_modify_target(mini_quixbugs):
    before = _snapshot(mini_quixbugs)
    engine_benchmark.evaluate_quixbugs_engine(mini_quixbugs)
    after = _snapshot(mini_quixbugs)
    assert before == after


# ---------------------------------------------------------------------------
# CLI dispatch: --engine legacy | unified
# ---------------------------------------------------------------------------
def test_cli_engine_unified_dispatch(mini_quixbugs, capsys):
    from builder_core import cli
    assert cli.main(["benchmark-quixbugs", "--project", mini_quixbugs, "--engine", "unified"]) == 0
    out = capsys.readouterr().out
    assert "QUIXBUGS BENCHMARK [engine=unified]" in out
    assert "precision: 1.0000" in out


def test_cli_engine_legacy_dispatch(mini_quixbugs, capsys):
    from builder_core import cli
    assert cli.main(["benchmark-quixbugs", "--project", mini_quixbugs, "--engine", "legacy"]) == 0
    out = capsys.readouterr().out
    assert "QUIXBUGS BENCHMARK" in out
    assert "engine=unified" not in out  # legacy formatter has no engine tag


def test_cli_default_engine_is_unified(mini_quixbugs, capsys):
    from builder_core import cli
    assert cli.main(["benchmark-quixbugs", "--project", mini_quixbugs]) == 0
    out = capsys.readouterr().out
    assert "engine=unified" in out  # default is the unified path
