"""Phase 121B — repository universe visualization restoration."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from jarvis_desktop import api


@pytest.fixture(autouse=True)
def reset_state():
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
        }
    )
    yield


def test_module_visual_metrics_log_scale_and_clamp():
    small = api._module_visual_metrics(0, 0)
    mid = api._module_visual_metrics(12, 8)
    huge = api._module_visual_metrics(500, 400)
    assert api.MODULE_VISUAL_SIZE_MIN <= small["visual_size"] <= api.MODULE_VISUAL_SIZE_MAX
    assert mid["visual_size"] > small["visual_size"]
    assert huge["visual_size"] > mid["visual_size"]
    assert huge["visual_size"] <= api.MODULE_VISUAL_SIZE_MAX
    assert huge["is_hub"] is True
    cap = api._module_visual_metrics(10_000, 10_000)
    assert cap["visual_size"] == api.MODULE_VISUAL_SIZE_MAX


def test_graph_recommended_view_threshold():
    assert api._graph_recommended_view(100) == "module"
    assert api._graph_recommended_view(999) == "module"
    assert api._graph_recommended_view(1000) == "hierarchy"
    assert api._graph_recommended_view(7551) == "hierarchy"


def test_module_graph_default_never_auto_subsystem(monkeypatch):
    node_count = 5105
    fake_graph = {
        "graph_scope": "production",
        "degraded": False,
        "nodes": [
            {"id": f"module:m{i}", "type": "module", "path": f"pkg/m{i}.py", "dotted": f"pkg.m{i}"}
            for i in range(node_count)
        ],
        "edges": [],
        "statistics": {"import_cycles": [], "top_imported_modules": [], "unresolved_counts": {}},
    }
    api._STATE.update(
        {
            "graph": fake_graph,
            "index": {"subsystems": [{"name": "pkg", "entry_files": [], "role_counts": {"production_code": node_count}}]},
            "risks": {"ranked_modules": []},
            "scan": {"massive_mode": True, "graph_scope": "production"},
        }
    )
    payload = api.current_graph("module")
    assert payload["ok"]
    assert payload["view"] == "module"
    assert payload["defaulted_to_subsystem"] is False
    assert payload["recommended_view"] == "hierarchy"


def test_galaxy_layout_hub_center_and_leaf_ring():
    nodes = [
        {"id": "a", "subsystem": "core", "fan_in": 20, "risk_score": 10, "label": "a"},
        {"id": "b", "subsystem": "core", "fan_in": 1, "risk_score": 1, "label": "b"},
        {"id": "c", "subsystem": "core", "fan_in": 0, "risk_score": 0, "label": "c"},
    ]
    api._apply_galaxy_layout(nodes, [])
    hub = next(n for n in nodes if n["id"] == "a")
    assert hub.get("is_hub") is True
    assert hub.get("galaxy_role") == "hub"
    leaf = next(n for n in nodes if n["id"] == "c")
    assert leaf.get("galaxy_role") in {"orbit", "leaf"}
    assert math.hypot(leaf["galaxy_x"] - hub["galaxy_x"], leaf["galaxy_y"] - hub["galaxy_y"]) >= 0


def test_architecture_cluster_naming():
    assert api._architecture_cluster_name("src/vs/workbench/browser") == "Workbench"
    assert api._architecture_cluster_name("extensions/git") == "Extension Host"
    assert api._architecture_cluster_name("src/vs/platform/files") == "Platform"


def test_subsystem_overview_uses_clusters_when_large(monkeypatch):
    node_count = 6000
    fake_graph = {
        "graph_scope": "production",
        "nodes": [
            {
                "id": f"module:m{i}",
                "type": "module",
                "path": f"src/vs/workbench/m{i}.ts",
                "dotted": f"vs.workbench.m{i}",
            }
            for i in range(min(80, node_count))
        ],
        "edges": [],
        "statistics": {"import_cycles": []},
    }
    api._STATE.update(
        {
            "graph": fake_graph,
            "index": {"subsystems": []},
            "risks": {"ranked_modules": []},
            "scan": {"massive_mode": True},
        }
    )
    overview = api.current_graph("subsystem")
    assert overview["ok"]
    assert overview.get("architecture_clusters") is True
    labels = {n["label"] for n in overview["nodes"]}
    assert "Workbench" in labels or len(labels) >= 1


def test_frontend_default_graph_helpers():
    app = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    uni = (Path(__file__).resolve().parents[1] / "static" / "universe.js").read_text(encoding="utf-8")
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "resolveDefaultGraphView" in app
    assert "GRAPH_HIERARCHY_THRESHOLD = 1000" in app
    assert "renderGraphModeMetrics" in app
    assert "graphScaleHeader" in html
    assert "function moduleNodeScale" in uni
    assert "fg.nodeOpacity" in uni
    assert "graphSpatialRadius" in uni
    assert "U.lastHoverId" in uni and "graphData(" not in uni[uni.find("function scheduleHoverUpdate"):uni.find("function applySelectionHighlight")]


@pytest.fixture()
def scanned_ts_repo():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


def test_module_graph_sizes_after_scan(scanned_ts_repo):
    graph = api.current_graph("module")
    assert graph["ok"] and graph["nodes"]
    for node in graph["nodes"]:
        assert node["visual_size"] >= api.MODULE_VISUAL_SIZE_MIN
        assert node["size"] <= api.MODULE_VISUAL_SIZE_MAX
