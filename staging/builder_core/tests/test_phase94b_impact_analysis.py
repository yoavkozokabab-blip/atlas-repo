"""Phase 94B tests: deterministic impact analysis."""

from __future__ import annotations

import textwrap

import pytest

from builder_core.bug_intelligence import depgraph, engine_benchmark, impact


def _graph(root: str, files):
    return depgraph.build_graph_from_files(root, [(p, textwrap.dedent(t)) for p, t in files])


def _analyze(graph, **kwargs):
    return impact.analyze_impact(graph, project_root="/repo", **kwargs)


def test_direct_and_transitive_function_impact():
    graph = _graph("/repo", [
        ("a.py", "import b\ndef fa():\n    return 1\n"),
        ("b.py", "import c\ndef fb():\n    return c.g()\n"),
        ("c.py", "def g():\n    return 1\n"),
    ])
    result = _analyze(graph, kind="function", function="c.py::g", include_transitive=True)
    fn_dep = {item["qualname"] for item in result["questions"]["functions_dependent"]}
    assert "fb" in fn_dep
    file_paths = {item["path"] for item in result["questions"]["files_dependent"]}
    assert "b.py" in file_paths
    assert result["questions"]["may_break"]["direct_count"] >= 1
    assert result["questions"]["may_break"]["transitive_count"] >= 1
    for item in result["questions"]["functions_dependent"]:
        assert item["evidence"]
        assert item["evidence"][0]["resolved"] is True
        assert item["evidence"][0]["line"] > 0


def test_star_import_is_possible_not_asserted():
    graph = _graph("/repo", [
        ("target.py", "def helper():\n    return 1\n"),
        ("consumer.py", "from target import *\ndef run():\n    return 1\n"),
    ])
    graph["unresolved"]["imports_external"].append({
        "from_module": "consumer.py",
        "line": 1,
        "target": "target",
        "reason": "star_import",
    })
    result = _analyze(graph, kind="file", file_path="target.py")
    reasons = {item["reason"] for item in result["possible_additional_impact"]}
    assert "star_import" in reasons
    assert result["confidence"]["bucket"] in ("medium", "low", "unknown")
    assert any("star_import" in c for c in result["confidence"].get("caveats", []))
    calls = [
        item for item in result["questions"]["functions_dependent"]
        if item.get("path") == "consumer.py"
    ]
    assert calls == []


def test_method_call_unresolved_verdict_unknown():
    graph = _graph("/repo", [
        ("m.py", textwrap.dedent("""
            class C:
                def m(self):
                    return super().other()
                def other(self):
                    return 1
        """)),
    ])
    result = _analyze(graph, kind="function", function="m.py::C.other")
    assert result["questions"]["functions_dependent"] == []
    assert result["possible_additional_impact"]
    assert result["confidence"]["bucket"] in ("unknown", "medium", "low")
    assert impact.exit_code(result) == 2


def test_parse_error_listed_unanalyzed():
    graph = _graph("/repo", [
        ("bad.py", "def oops(\n"),
        ("good.py", "def ok():\n    return 1\n"),
    ])
    result = _analyze(graph, kind="file", file_path="good.py")
    assert "bad.py" in result["unanalyzed"]


def test_module_indegree_matches_statistics():
    graph = _graph("/repo", [
        ("a.py", "import b\ndef fa():\n    return 1\n"),
        ("b.py", "import c\ndef fb():\n    return 1\n"),
        ("c.py", "def fc():\n    return 1\n"),
    ])
    result = _analyze(graph, kind="module", module="c")
    assert result["questions"]["import_indegree_check_ok"] is True
    assert len(result["questions"]["modules_importing"]) == 1


def test_deterministic_json_bytes():
    files = [
        ("b.py", "def g():\n    return 1\n"),
        ("a.py", "import b\ndef f():\n    return b.g()\n"),
    ]
    first = impact.export_json(_analyze(_graph("/repo", files), kind="function", function="b.py::g"))
    second = impact.export_json(_analyze(_graph("/repo", list(reversed(files))), kind="function", function="b.py::g"))
    assert first == second


def test_modules_importing_question():
    graph = _graph("/repo", [
        ("pkg/__init__.py", ""),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("pkg/main.py", "from pkg.util import helper\n\ndef run():\n    return helper()\n"),
    ])
    result = _analyze(graph, kind="module", module="pkg.util")
    assert len(result["questions"]["modules_importing"]) == 1
    assert result["questions"]["modules_importing"][0]["path"] == "pkg/main.py"


def test_degraded_graph_unknown_confidence():
    graph = depgraph._degraded_graph("/repo", "too_many_files", 99999)
    result = _analyze(graph, kind="file", file_path="x.py")
    assert result["confidence"]["bucket"] == "unknown"
    assert impact.exit_code(result) == 2


def test_target_not_found():
    graph = _graph("/repo", [("m.py", "def f():\n    return 1\n")])
    result = _analyze(graph, kind="function", function="m.py::missing")
    assert result.get("error")
    assert impact.exit_code(result) == 2


def test_benchmark_unchanged(tmp_path):
    root = tmp_path / "MiniQuixBugs"
    buggy = root / "python_programs"
    correct = root / "correct_python_programs"
    buggy.mkdir(parents=True)
    correct.mkdir()
    bfs = textwrap.dedent("""
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
                queue.extend(n for n in node.successors if n not in nodesseen)
                nodesseen.update(node.successors)
            return False
    """)
    (buggy / "breadth_first_search.py").write_text(bfs, encoding="utf-8")
    (correct / "breadth_first_search.py").write_text(
        bfs.replace("while True:", "while queue:"), encoding="utf-8")
    report = engine_benchmark.evaluate_quixbugs_engine(str(root))
    assert report["true_positives"] == 1
    assert report["false_positives"] == 0

    holdout = engine_benchmark.evaluate_holdout_engine(pairs_root=tmp_path / "nope")
    assert holdout["available"] is False


def test_impact_cli_smoke(tmp_path, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "b.py").write_text("import a\ndef g():\n    return a.f()\n", encoding="utf-8")
    from builder_core import cli

    rc = cli.main(["impact-function", "--project", str(root), "a.py::f"])
    out = capsys.readouterr().out
    assert rc in (0, 2)
    assert "IMPACT ANALYSIS" in out
    assert "FUNCTIONS DEPENDENT" in out


def test_impact_file_cli(tmp_path, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "target.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    from builder_core import cli

    rc = cli.main(["impact-file", "--project", str(root), "target.py"])
    out = capsys.readouterr().out
    assert rc in (0, 2)
    assert "IMPACT ANALYSIS" in out
    assert "target.py" in out


def test_impact_module_cli(tmp_path, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    from builder_core import cli

    rc = cli.main(["impact-module", "--project", str(root), "m"])
    out = capsys.readouterr().out
    assert rc in (0, 2)
    assert "MODULES IMPORTING" in out


def test_impact_paths_cli(tmp_path, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    from builder_core import cli

    rc = cli.main(["impact-paths", "--project", str(root), "m.py::f"])
    out = capsys.readouterr().out
    assert rc in (0, 2)
    assert "EXECUTION PATHS" in out
