"""Phase 116G regressions for production scope and canonical cycles."""

from __future__ import annotations

from pathlib import Path

import pytest

from builder_core import architectural_risk, repository_understanding
from builder_core.bug_intelligence import depgraph, jsdepgraph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("docs_src/tutorial/body_fields/tutorial001.py", "general_doc"),
        ("docs/tutorial/example.py", "general_doc"),
        ("examples/quickstart.py", "general_doc"),
        ("fixtures/sample_app.py", "dataset"),
        ("testdata/generated_case.py", "dataset"),
        ("generated_snippets/client.py", "generated"),
        ("src/fixtures_service.py", "production_code"),
        ("src/examples_api.py", "production_code"),
    ],
)
def test_role_classifier_excludes_nonproduction_code_trees_without_substring_overfilter(path, role):
    assert repository_understanding.classify_file_role(path) == role


def test_python_production_graph_excludes_docs_examples_and_fixture_trees(tmp_path):
    root = tmp_path / "repo"
    _write(root / "src" / "service.py", "def run():\n    return True\n")
    _write(root / "docs_src" / "tutorial" / "demo.py", "def docs_demo():\n    return True\n")
    _write(root / "examples" / "quickstart.py", "def example():\n    return True\n")
    _write(root / "fixtures" / "case.py", "def fixture():\n    return True\n")

    graph = depgraph.build_graph(str(root))
    module_paths = {
        node["path"] for node in graph["nodes"] if node.get("type") == "module"
    }

    assert module_paths == {"src/service.py"}
    excluded = graph["scope_diagnostics"]["excluded_by_role"]
    assert excluded["general_doc"] == 2
    assert excluded["dataset_tree"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "docs_src/tutorial/demo.ts",
        "docs/example.js",
        "examples/quickstart.tsx",
        "fixtures/case.js",
        "testdata/case.ts",
        "generated_snippets/client.js",
    ],
)
def test_javascript_production_graph_excludes_nonproduction_code_trees(path):
    assert jsdepgraph.is_production_js_file(path) is False


def test_javascript_production_graph_keeps_real_source_with_similar_filename():
    assert jsdepgraph.is_production_js_file("src/examples_api.ts") is True
    assert jsdepgraph.is_production_js_file("src/fixtures_service.js") is True


def test_cycle_identity_is_rotation_and_reverse_invariant():
    expected = depgraph._canonical_cycle(["module:a.py", "module:b.py", "module:c.py", "module:a.py"])
    assert depgraph._canonical_cycle(["module:b.py", "module:c.py", "module:a.py", "module:b.py"]) == expected
    assert depgraph._canonical_cycle(["module:c.py", "module:b.py", "module:a.py", "module:c.py"]) == expected
    assert architectural_risk._canonical_cycle(
        ["module:c.py", "module:b.py", "module:a.py", "module:c.py"]
    ) == expected


def test_two_node_cycle_is_reported_once():
    edges = [
        {"type": "imports", "from": "module:a.py", "to": "module:b.py", "resolved": True},
        {"type": "imports", "from": "module:b.py", "to": "module:a.py", "resolved": True},
    ]

    assert depgraph._import_cycles(edges) == [["module:a.py", "module:b.py", "module:a.py"]]
    assert depgraph._import_cycles_bounded(edges) == [["module:a.py", "module:b.py", "module:a.py"]]
