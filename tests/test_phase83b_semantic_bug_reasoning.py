"""Phase 83B semantic bug reasoning tests."""

from __future__ import annotations

from pathlib import Path

from builder_core import ask, benchmark, cli, indexer
from builder_core.algorithm_profiles import PROFILES, detect_profiles
from builder_core.python_analysis import analyze_python

BUGGY_BFS = """\
from node import Node
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
            queue.extend(node for node in node.successors if node not in nodesseen)
            nodesseen.update(node.successors)
    return False
"""

CORRECT_BFS = BUGGY_BFS.replace("    while True:\n", "    while queue:\n")

BFS_TEST = """\
from python_programs.breadth_first_search import breadth_first_search

def test_unreachable_graph(node1, node5):
    assert not breadth_first_search(node1, node5)
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _test_documents() -> list[dict[str, str]]:
    return [
        {
            "path": "python_testcases/test_breadth_first_search.py",
            "text": BFS_TEST,
        }
    ]


def _semantic_rules(analysis: dict) -> set[str]:
    return {
        item["rule"]
        for item in analysis["findings"]
        if item.get("kind") == "semantic"
    }


def test_required_algorithm_profiles_exist() -> None:
    assert {profile.name for profile in PROFILES} == {
        "bfs",
        "dfs",
        "shortest_path",
        "sorting",
        "recursion",
        "graph_traversal",
        "tree_traversal",
        "dynamic_programming",
    }


def test_profile_detection_uses_names_docstrings_and_source_vocabulary() -> None:
    assert {item.name for item in detect_profiles("breadth_first_search")} >= {"bfs"}
    assert {item.name for item in detect_profiles("walk", "recursive tree traversal")} >= {
        "recursion",
        "tree_traversal",
    }
    assert {item.name for item in detect_profiles("knapsack")} >= {"dynamic_programming"}
    assert {item.name for item in detect_profiles("shortest_path")} >= {"shortest_path"}
    assert {item.name for item in detect_profiles("merge_sort")} >= {"sorting"}


def test_quixbugs_bfs_explains_frontier_exhaustion_and_test_mismatch() -> None:
    analysis = analyze_python(
        "python_programs/breadth_first_search.py",
        BUGGY_BFS,
        test_documents=_test_documents(),
    )

    assert "bfs" in analysis["algorithm_profiles"]
    assert "bfs_queue_exhaustion" in _semantic_rules(analysis)
    finding = next(
        item
        for item in analysis["findings"]
        if item["rule"] == "bfs_queue_exhaustion"
    )
    assert "frontier empties" in finding["message"]
    assert "returning False" in finding["message"]
    assert "Indexed tests expect False" in finding["message"]
    assert "bfs_cycle_handling" not in _semantic_rules(analysis)
    assert analysis["test_expectations"][0]["type"] == "returns_false_when_unreachable"


def test_corrected_quixbugs_bfs_does_not_report_semantic_defect() -> None:
    analysis = analyze_python(
        "correct_python_programs/breadth_first_search.py",
        CORRECT_BFS,
        test_documents=_test_documents(),
    )

    assert "bfs_queue_exhaustion" not in _semantic_rules(analysis)
    assert "bfs_fifo_violation" not in _semantic_rules(analysis)
    assert "bfs_cycle_handling" not in _semantic_rules(analysis)


def test_bfs_stack_behavior_is_reported_as_fifo_violation() -> None:
    analysis = analyze_python(
        "breadth_first_search.py",
        """\
def breadth_first_search(start, goal):
    queue = [start]
    seen = {start}
    while queue:
        node = queue.pop()
        if node is goal:
            return True
        queue.extend(node for node in node.successors if node not in seen)
        seen.update(node.successors)
    return False
""",
    )

    assert "bfs_fifo_violation" in _semantic_rules(analysis)


def test_ask_surfaces_semantic_bfs_explanation() -> None:
    analysis = analyze_python(
        "python_programs/breadth_first_search.py",
        BUGGY_BFS,
        test_documents=_test_documents(),
    )
    result = ask.answer(
        {"python_analysis": [analysis]},
        "Analyze python_programs/breadth_first_search.py for likely bugs and logic errors.",
    )

    assert result["mode"] == "python_analysis"
    assert "algorithm-invariant violation" in result["answer"]
    assert "frontier empties" in result["answer"]
    assert "python_testcases/test_breadth_first_search.py" in result["sources"]


def test_benchmark_quixbugs_compares_buggy_and_correct_files(tmp_path: Path) -> None:
    _write(tmp_path / "python_programs" / "breadth_first_search.py", BUGGY_BFS)
    _write(tmp_path / "correct_python_programs" / "breadth_first_search.py", CORRECT_BFS)
    _write(tmp_path / "python_testcases" / "test_breadth_first_search.py", BFS_TEST)

    report = benchmark.evaluate_quixbugs(str(tmp_path))

    assert report["available"] is True
    assert report["buggy_files_analyzed"] == 1
    assert report["correct_files_analyzed"] == 1
    assert report["true_positives"] == 1
    assert report["false_positives"] == 0
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert report["true_positive_rate"] == 1.0
    assert report["false_positive_rate"] == 0.0
    assert report["breadth_first_search"]["findings"][0]["rule"] == "bfs_queue_exhaustion"


def test_cli_benchmark_quixbugs_prints_semantic_metrics(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "python_programs" / "breadth_first_search.py", BUGGY_BFS)
    _write(tmp_path / "correct_python_programs" / "breadth_first_search.py", CORRECT_BFS)
    _write(tmp_path / "python_testcases" / "test_breadth_first_search.py", BFS_TEST)

    assert cli.main(["benchmark-quixbugs", "--project", str(tmp_path)]) == 0
    output = capsys.readouterr().out

    assert "buggy files analyzed: 1" in output
    assert "correct files analyzed: 1" in output
    assert "true positives: 1" in output
    assert "false positives: 0" in output
    assert "bfs_queue_exhaustion" in output


def test_benchmark_and_analysis_do_not_write_target_repo(tmp_path: Path) -> None:
    _write(tmp_path / "python_programs" / "breadth_first_search.py", BUGGY_BFS)
    _write(tmp_path / "correct_python_programs" / "breadth_first_search.py", CORRECT_BFS)
    _write(tmp_path / "python_testcases" / "test_breadth_first_search.py", BFS_TEST)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    benchmark.evaluate_quixbugs(str(tmp_path))
    indexer.build_index(str(tmp_path))
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert after == before
