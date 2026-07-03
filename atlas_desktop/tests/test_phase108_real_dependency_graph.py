"""Phase 108 — real dependency graph payload and repository differentiation."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _small_repo(tmp_path: Path) -> Path:
    root = tmp_path / "small"
    _write(root / "core" / "hub.py", "def hub():\n    return 1\n")
    for name in ("a", "b"):
        _write(root / f"{name}.py", f"from core.hub import hub\n\ndef run_{name}():\n    return hub()\n")
    return root


def _wide_repo(tmp_path: Path) -> Path:
    root = tmp_path / "wide"
    _write(root / "shared" / "base.py", "def base():\n    return 0\n")
    for idx in range(12):
        _write(
            root / f"pkg{idx}" / f"m{idx}.py",
            "from shared.base import base\n\n\ndef run():\n    return base()\n",
        )
    return root


@pytest.fixture()
def small_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    result = api.scan_repository(str(_small_repo(tmp_path)))
    assert result["ok"], result
    return result


@pytest.fixture()
def wide_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    result = api.scan_repository(str(_wide_repo(tmp_path)))
    assert result["ok"], result
    return result


def test_module_graph_matches_scan_counts(small_scan):
    graph = api.current_graph("module")
    assert graph["ok"]
    assert graph["view"] == "module"
    assert graph["node_count"] == small_scan["module_count"]
    assert graph["link_count"] == small_scan["dependency_edges"]
    assert graph["total_modules"] == small_scan["module_count"]
    assert graph["total_edges"] == small_scan["dependency_edges"]
    node = graph["nodes"][0]
    for key in (
        "id",
        "label",
        "path",
        "subsystem",
        "fan_in",
        "fan_out",
        "loc",
        "risk_score",
        "risk_tier",
        "in_cycle",
        "size",
        "importers_count",
        "imported_modules_count",
    ):
        assert key in node, key
    link = graph["links"][0]
    assert "opacity" in link and "weight" in link


def test_subsystem_graph_collapses_modules(small_scan):
    module_graph = api.current_graph("module")
    subsystem_graph = api.current_graph("subsystem")
    assert subsystem_graph["ok"]
    assert subsystem_graph["view"] == "subsystem"
    assert subsystem_graph["node_count"] <= module_graph["node_count"]
    assert subsystem_graph["node_count"] >= 1
    assert all(node["id"].startswith("subsystem:") for node in subsystem_graph["nodes"])


def test_different_repositories_produce_different_graphs(tmp_path, small_scan):
    small = api.current_graph("module")
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    wide = api.scan_repository(str(_wide_repo(tmp_path)))
    assert wide["ok"]
    wide_graph = api.current_graph("module")
    assert small["node_count"] != wide_graph["node_count"]
    assert small["link_count"] != wide_graph["link_count"]
    assert {n["id"] for n in small["nodes"]} != {n["id"] for n in wide_graph["nodes"]}


def test_risk_tiers_follow_ranking(small_scan):
    graph = api.current_graph("module")
    tiers = {node["risk_tier"] for node in graph["nodes"]}
    assert tiers  # at least one tier present
    cycle_nodes = [n for n in graph["nodes"] if n["in_cycle"]]
    for node in cycle_nodes:
        assert node["risk_tier"] == "cycle"


def test_product_repo_graph_is_non_trivial():
    repo_root = Path(__file__).resolve().parents[2]
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    scan = api.scan_repository(str(repo_root))
    assert scan["ok"]
    graph = api.current_graph("module")
    assert graph["node_count"] >= 50
    assert graph["link_count"] >= 50
    assert graph["node_count"] == scan["module_count"] or graph["node_count"] <= api.GRAPH_DISPLAY_CAP
    assert graph["total_edges"] == scan["dependency_edges"]
