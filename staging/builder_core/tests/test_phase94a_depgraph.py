"""Phase 94A tests: deterministic dependency graph."""

from __future__ import annotations

import textwrap

import pytest

from builder_core.bug_intelligence import depgraph, engine, engine_benchmark


def _graph(root: str, files):
    return depgraph.build_graph_from_files(root, [(p, textwrap.dedent(t)) for p, t in files])


def _edge_types(graph, etype):
    return [e for e in graph["edges"] if e["type"] == etype]


def _nodes(graph, ntype):
    return [n for n in graph["nodes"] if n["type"] == ntype]


def test_module_level_class_does_not_crash():
    """Regression: ClassDef nodes are not in callgraph._compute_qualnames."""
    graph = _graph("/repo", [
        ("actions/app_actions.py", textwrap.dedent("""
            class DiscoverAppsAction:
                pass
        """)),
    ])
    classes = _nodes(graph, "class")
    assert len(classes) == 1
    assert classes[0]["qualname"] == "DiscoverAppsAction"
    assert classes[0]["path"] == "actions/app_actions.py"
    contains = _edge_types(graph, "contains")
    assert any(
        e["to"] == classes[0]["id"] and e["from"] == "module:actions/app_actions.py"
        for e in contains
    )


def test_nested_class_does_not_crash():
    """Nested classes must not crash index/build; top-level class becomes a node."""
    graph = _graph("/repo", [
        ("m.py", textwrap.dedent("""
            class Outer:
                class Inner:
                    pass
        """)),
    ])
    classes = _nodes(graph, "class")
    assert len(classes) == 1
    assert classes[0]["qualname"] == "Outer"


def test_contains_hierarchy_small_repo():
    graph = _graph("/repo", [
        ("pkg/__init__.py", ""),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("pkg/main.py", "from pkg.util import helper\n\ndef run():\n    return helper()\n"),
    ])
    modules = {n["path"] for n in _nodes(graph, "module")}
    assert modules == {"pkg/__init__.py", "pkg/util.py", "pkg/main.py"}
    contains = _edge_types(graph, "contains")
    assert any(e["from"].startswith("repository:") and e["to"] == "module:pkg/util.py"
               for e in contains)
    fn = [n for n in _nodes(graph, "function") if n["qualname"] == "helper"]
    assert len(fn) == 1
    assert any(e["to"] == fn[0]["id"] for e in contains)


def test_cross_file_call_edge():
    graph = _graph("/repo", [
        ("a.py", "def f():\n    return 1\n"),
        ("b.py", "import a\ndef g():\n    return a.f()\n"),
    ])
    calls = _edge_types(graph, "calls")
    cross = [e for e in calls if e.get("scope") == "cross_file"]
    assert len(cross) == 1
    assert cross[0]["from"] == "function:b.py::g"
    assert cross[0]["to"] == "function:a.py::f"


def test_intra_file_call_edge():
    graph = _graph("/repo", [
        ("m.py", "def a():\n    return b()\ndef b():\n    return 1\n"),
    ])
    calls = _edge_types(graph, "calls")
    assert any(e["from"] == "function:m.py::a" and e["to"] == "function:m.py::b"
               for e in calls)


def test_unresolved_external_import_not_project_edge():
    graph = _graph("/repo", [
        ("main.py", "import requests\ndef run():\n    return requests.get('x')\n"),
    ])
    imports = _edge_types(graph, "imports")
    assert imports == []
    assert graph["unresolved"]["imports_external"]
    assert graph["statistics"]["unresolved_counts"]["imports_external"] >= 1


def test_unresolved_call_not_edge():
    graph = _graph("/repo", [
        ("m.py", "def a():\n    return unknown()\n"),
    ])
    calls = _edge_types(graph, "calls")
    assert calls == []
    assert graph["unresolved"]["calls_unresolved"]


def test_import_cycle_detected():
    graph = _graph("/repo", [
        ("a.py", "import b\ndef fa():\n    return 1\n"),
        ("b.py", "import a\ndef fb():\n    return 1\n"),
    ])
    cycles = graph["statistics"]["import_cycles"]
    assert cycles
    assert any("module:a.py" in cycle and "module:b.py" in cycle for cycle in cycles)


def test_imports_resolved_between_project_modules():
    graph = _graph("/repo", [
        ("pkg/__init__.py", ""),
        ("pkg/util.py", "def helper():\n    return 1\n"),
        ("pkg/main.py", "from pkg.util import helper\n\ndef run():\n    return helper()\n"),
    ])
    imports = _edge_types(graph, "imports")
    assert any(e["from"] == "module:pkg/main.py" and e["to"] == "module:pkg/util.py"
               for e in imports)


def test_parse_error_module_node_without_contents():
    graph = _graph("/repo", [
        ("bad.py", "def oops(\n"),
        ("good.py", "def ok():\n    return 1\n"),
    ])
    bad = next(n for n in _nodes(graph, "module") if n["path"] == "bad.py")
    assert bad["parse_ok"] is False
    good_fns = [n for n in _nodes(graph, "function") if n["path"] == "good.py"]
    assert len(good_fns) == 1


def test_export_is_deterministic():
    files = [
        ("b.py", "def g():\n    return 1\n"),
        ("a.py", "import b\ndef f():\n    return b.g()\n"),
    ]
    first = depgraph.export_json(_graph("/repo", files))
    second = depgraph.export_json(_graph("/repo", list(reversed(files))))
    assert first == second


def test_statistics_top_lists():
    graph = _graph("/repo", [
        ("a.py", "def f():\n    return 1\n"),
        ("b.py", "import a\ndef g():\n    return a.f()\n"),
        ("c.py", "import a\ndef h():\n    return a.f()\n"),
    ])
    stats = graph["statistics"]
    assert stats["total_nodes"] >= 4
    assert stats["edge_counts"]["calls"] >= 2
    top_called = stats["top_called_functions"]
    assert top_called and top_called[0]["qualname"] == "f"


def test_engine_entry_point():
    graph = engine.build_dependency_graph("/repo")
    assert graph["schema_version"] == depgraph.GRAPH_SCHEMA_VERSION


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


def test_build_graph_cli_smoke(tmp_path, capsys):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    from builder_core import cli

    assert cli.main(["graph", "build", "--project", str(root)]) == 0
    assert "DEPENDENCY GRAPH BUILT" in capsys.readouterr().out
