"""Phase 100G — dependency-graph production-scope filter regressions.

The production scope reuses the RU-2 role classifier (plus a top-level data-tree
exclusion) so generated/runtime/data/benchmark/report/test files do not push the
graph over the cap and trigger degraded mode on large repositories.
"""

from __future__ import annotations

from pathlib import Path

from builder_core import ask
from builder_core.bug_intelligence import depgraph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _noisy_repo(tmp_path: Path) -> Path:
    """A repo whose non-production files outnumber its production source."""
    root = tmp_path / "repo"
    # production source (kept) — a fan-in hub + importers + an import cycle
    _write(root / "core" / "util.py", '"""hub."""\n\n\ndef helper():\n    return 1\n')
    for name in ("a", "b", "c"):
        _write(root / f"{name}.py", f"from core.util import helper\n\n\ndef run_{name}():\n    return helper()\n")
    _write(root / "ring" / "x.py", "from ring.y import gy\n\n\ndef gx():\n    return gy()\n")
    _write(root / "ring" / "y.py", "from ring.x import gx\n\n\ndef gy():\n    return 1\n")
    # data corpus: .py classifies as production_code by ROLE but lives under data/
    for i in range(8):
        _write(root / "data" / "corpus" / f"vendor_{i}.py", f"def f_{i}():\n    return {i}\n")
    # generated / report / test (non-production roles)
    _write(root / "generated" / "g.py", "def gen():\n    return 0\n")
    _write(root / "reports" / "r.py", "def rep():\n    return 0\n")
    _write(root / "tests" / "test_core.py", "def test_x():\n    assert True\n")
    return root


def test_production_scope_excludes_noise_and_does_not_degrade(tmp_path, monkeypatch):
    # tiny file cap: the full file set trips it, the production subset must not
    monkeypatch.setattr(depgraph, "_MAX_FILES", 6)
    root = _noisy_repo(tmp_path)

    full = depgraph.build_graph(str(root), scope="full")
    assert full["graph_scope"] == "degraded"  # all files over the tiny cap

    prod = depgraph.build_graph(str(root))  # production is the default
    assert prod["graph_scope"] == "production"
    assert not prod.get("degraded")


def test_scope_diagnostics_report_filtering(tmp_path):
    root = _noisy_repo(tmp_path)
    diag = depgraph.build_graph(str(root))["scope_diagnostics"]
    assert diag["requested_scope"] == "production"
    assert diag["total_candidate_files"] > diag["files_kept"]
    assert diag["files_excluded"] == diag["total_candidate_files"] - diag["files_kept"]
    excluded = diag["excluded_by_role"]
    assert excluded.get("dataset_tree", 0) >= 8   # data/ .py excluded by location
    assert "generated" in excluded
    assert "report_history" in excluded
    assert "test" in excluded
    assert diag["cap_files"] == depgraph._MAX_FILES


def test_production_files_kept_and_noise_excluded(tmp_path):
    root = _noisy_repo(tmp_path)
    graph = depgraph.build_graph(str(root))
    module_paths = {n["path"] for n in graph["nodes"] if n.get("type") == "module"}
    # production source kept
    assert "core/util.py" in module_paths
    assert "a.py" in module_paths
    # noise excluded
    assert not any(p.startswith("data/") for p in module_paths)
    assert not any(p.startswith("generated/") for p in module_paths)
    assert not any(p.startswith("reports/") for p in module_paths)
    assert not any(p.startswith("tests/") for p in module_paths)


def test_include_tests_keeps_tests(tmp_path):
    root = _noisy_repo(tmp_path)
    graph = depgraph.build_graph(str(root), include_tests=True)
    module_paths = {n["path"] for n in graph["nodes"] if n.get("type") == "module"}
    assert any("test" in p for p in module_paths)
    # data tree still excluded even with tests included
    assert not any(p.startswith("data/") for p in module_paths)


def test_full_scope_keeps_everything(tmp_path):
    root = _noisy_repo(tmp_path)
    graph = depgraph.build_graph(str(root), scope="full")
    module_paths = {n["path"] for n in graph["nodes"] if n.get("type") == "module"}
    assert any(p.startswith("data/") for p in module_paths)  # legacy: nothing filtered
    assert graph["scope_diagnostics"]["requested_scope"] == "full"


def test_bottleneck_query_returns_ranking_despite_data_noise(tmp_path):
    root = _noisy_repo(tmp_path)
    index = {"project_root": str(root), "files": [], "subsystems": [], "python_analysis": []}
    result = ask.answer(
        index,
        "Rank the top architectural risk modules using dependency graph fan-in and import cycles.",
    )
    assert result["mode"] == "bottleneck"
    answer = result["answer"].lower()
    assert "based on the indexed project" not in answer   # not retrieval fallback
    assert "degraded" not in answer                        # not degraded mode
    joined = (result["answer"] + " ".join(result["evidence"])).lower()
    assert "fan-in" in joined                              # real graph ranking
    assert "core" in joined                                # the fan-in hub
    # the data-corpus modules must not appear in the architectural ranking
    assert "vendor_" not in joined
    assert result["interpretation"]["graph_scope"] == "production"
