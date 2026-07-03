"""Phase 115B — dependency graph performance tiers and import-only fast path."""

from __future__ import annotations

from pathlib import Path

from builder_core.bug_intelligence import cross_file, depgraph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mini_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "a.py", "import b\n\ndef fa():\n    return 1\n")
    _write(root / "b.py", "def fb():\n    return 2\n")
    return root


def test_imports_detail_matches_module_import_edges(tmp_path):
    root = _mini_repo(tmp_path)
    full = depgraph.build_graph(str(root), detail=depgraph.DETAIL_FULL)
    fast = depgraph.build_graph(str(root), detail=depgraph.DETAIL_IMPORTS)
    full_imports = {
        (e["from"], e["to"])
        for e in full["edges"]
        if e.get("type") == "imports" and e.get("resolved")
    }
    fast_imports = {
        (e["from"], e["to"])
        for e in fast["edges"]
        if e.get("type") == "imports" and e.get("resolved")
    }
    assert fast_imports == full_imports
    assert not any(n.get("type") == "function" for n in fast["nodes"])


def test_cross_file_from_parsed_avoids_double_parse(tmp_path, monkeypatch):
    root = _mini_repo(tmp_path)
    parse_count = {"n": 0}
    original = __import__("ast").parse

    def counted_parse(src, *args, **kwargs):
        parse_count["n"] += 1
        return original(src, *args, **kwargs)

    monkeypatch.setattr("ast.parse", counted_parse)
    depgraph.build_graph(str(root), detail=depgraph.DETAIL_FULL)
    # one parse per file in depgraph; cross_file must not re-parse
    assert parse_count["n"] == 2


def test_time_budget_returns_partial_graph(tmp_path, monkeypatch):
    root = _mini_repo(tmp_path)
    calls = {"n": 0}
    real_mono = __import__("time").monotonic

    def fake_mono():
        calls["n"] += 1
        return 1e12 if calls["n"] > 3 else 0.0

    monkeypatch.setattr(depgraph.time, "monotonic", fake_mono)
    graph = depgraph.build_graph(str(root), detail=depgraph.DETAIL_FULL, time_budget_sec=60.0)
    assert graph.get("atlas_partial") or graph.get("atlas_timed_out")
