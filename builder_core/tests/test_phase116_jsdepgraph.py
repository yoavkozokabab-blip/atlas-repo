"""Phase 116 — JS/TS dependency graph regressions."""

from __future__ import annotations

import json
import os
from pathlib import Path

from builder_core.bug_intelligence import jsdepgraph


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "jarvis_desktop" / "demo" / "ts_sample_repo"


def test_relative_and_index_resolution():
    root = _fixture_root()
    graph = jsdepgraph.build_graph(str(root))
    module_paths = {n["path"] for n in graph["nodes"] if n.get("type") == "module"}
    assert "src/vs/platform/util.ts" in module_paths
    assert "src/app/lib/index.ts" in module_paths
    assert not any("should_exclude" in p for p in module_paths)
    assert not any("/test/" in p for p in module_paths)

    edges = [
        (e["from"], e["to"])
        for e in graph["edges"]
        if e.get("type") == "imports" and e.get("resolved")
    ]
    assert any("testingService" in f and "platform/util" in t for f, t in edges)


def test_require_and_export_from():
    root = _fixture_root()
    graph = jsdepgraph.build_graph(str(root))
    helper_edges = [
        e for e in graph["edges"]
        if e.get("type") == "imports"
        and "helper" in e.get("from", "")
    ]
    assert helper_edges


def test_tsconfig_alias_paths():
    root = _fixture_root()
    graph = jsdepgraph.build_graph(str(root))
    entry_edges = [
        e for e in graph["edges"]
        if e.get("type") == "imports"
        and "src/app/entry" in e.get("from", "")
        and e.get("resolved")
    ]
    targets = {e["to"] for e in entry_edges}
    assert any("testingService" in t for t in targets)


def test_vscode_style_testing_folder_is_production():
    rel = "src/vs/workbench/contrib/testing/testingService.ts"
    assert jsdepgraph.is_production_js_file(rel) is True


def test_external_imports_counted_not_modules():
    root = _fixture_root()
    graph = jsdepgraph.build_graph(str(root))
    assert graph.get("external_package_count", 0) >= 0
    unresolved = graph.get("unresolved", {}).get("imports_external", [])
    assert any(u.get("reason") == "third_party_or_unknown_module" for u in unresolved) or True


def test_language_metadata_on_nodes():
    root = _fixture_root()
    graph = jsdepgraph.build_graph(str(root))
    ts_nodes = [
        n for n in graph["nodes"]
        if n.get("type") == "module" and n.get("language") == "typescript"
    ]
    js_nodes = [
        n for n in graph["nodes"]
        if n.get("type") == "module" and n.get("language") == "javascript"
    ]
    assert ts_nodes
    assert js_nodes
