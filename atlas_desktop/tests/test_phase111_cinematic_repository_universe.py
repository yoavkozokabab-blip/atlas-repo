"""Phase 111 — cinematic 3D repository universe (visualization layer)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api
from atlas_desktop import server


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _small_repo(tmp_path: Path) -> Path:
    root = tmp_path / "galaxy"
    _write(root / "voice" / "stt.py", "def listen():\n    return True\n")
    _write(root / "voice" / "tts.py", "from voice.stt import listen\n\ndef speak():\n    return listen()\n")
    _write(root / "builder_core" / "hub.py", "def hub():\n    return 1\n")
    _write(root / "assistant" / "app.py", "from builder_core.hub import hub\nfrom voice.tts import speak\n\ndef run():\n    return hub() and speak()\n")
    return root


@pytest.fixture()
def scanned(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    result = api.scan_repository(str(_small_repo(tmp_path)))
    assert result["ok"], result
    return result


def test_graph_node_count_matches_scan(scanned):
    graph = api.current_graph("module")
    assert graph["ok"]
    assert graph["node_count"] == scanned["module_count"]
    assert graph["link_count"] == scanned["dependency_edges"]
    assert graph["layout"] == "galaxy"
    assert graph["cluster_count"] >= 2
    assert graph["clusters"]
    for node in graph["nodes"]:
        assert "galaxy_x" in node and "galaxy_y" in node and "galaxy_z" in node
        assert "cluster_id" in node


def test_subsystem_clusters_have_hubs(scanned):
    graph = api.current_graph("module")
    hubs = [n for n in graph["nodes"] if n.get("is_hub")]
    assert len(hubs) == graph["cluster_count"]
    cluster_ids = {c["id"] for c in graph["clusters"]}
    assert all(h["cluster_id"] in cluster_ids for h in hubs)


def test_bridge_links_mark_cross_subsystem_edges(scanned):
    graph = api.current_graph("module")
    assert graph["bridge_link_count"] >= 1
    assert any(link.get("bridge") for link in graph["links"])


def test_timeline_api(scanned):
    timeline = api.current_timeline()
    assert timeline["ok"]
    assert timeline["snapshots"]
    latest = timeline["latest"]
    assert latest["module_count"] == scanned["module_count"]
    assert latest["dependency_count"] == scanned["dependency_edges"]
    assert latest["cycle_count"] == scanned["import_cycle_count"]


def test_tour_api_has_five_stops(scanned):
    tour = api.current_tour("module")
    assert tour["ok"]
    assert tour["stop_count"] == 5
    steps = [stop["step"] for stop in tour["stops"]]
    assert steps == [
        "largest_subsystem",
        "critical_hubs",
        "import_cycles",
        "highest_risks",
        "entry_points",
    ]


def test_module_inspector_uses_real_scan_data(scanned):
    graph = api.current_graph("module")
    sample = graph["nodes"][0]
    info = api.module_inspector(sample["path"])
    assert info["ok"]
    assert info["path"] == sample["path"]
    assert info["subsystem"] == sample["subsystem"]
    assert "importers" in info and "imports" in info
    assert "evidence" in info
    assert "blast_radius" in info


def test_impact_returns_node_ids_for_graph_highlight(scanned):
    graph = api.current_graph("module")
    target = graph["nodes"][0]["path"]
    payload = api.impact(target)
    assert payload["ok"]
    assert payload.get("target_node_id")
    assert isinstance(payload.get("affected_node_ids"), list)


def test_copilot_impact_includes_graph_highlight(scanned):
    graph = api.current_graph("module")
    target = graph["nodes"][0]["path"]
    res = api.copilot_ask(f"What breaks if I change {target}?")
    assert res["ok"]
    assert res["mode"] == "impact"
    highlight = res.get("graph_highlight") or {}
    assert highlight.get("kind") == "blast_radius"
    assert highlight.get("target_node_id")
    assert isinstance(highlight.get("node_ids"), list)


def test_server_routes_phase111(scanned):
    status, payload = server.dispatch("GET", "/api/repositories/current/timeline")
    assert status == 200
    assert "snapshots" in payload
    status, payload = server.dispatch("GET", "/api/repositories/current/tour")
    assert status == 200
    assert "stops" in payload


def test_frontend_universe_markers_exist():
    static = Path(__file__).resolve().parents[1] / "static"
    app = (static / "app.js").read_text(encoding="utf-8")
    universe = (static / "universe.js").read_text(encoding="utf-8")
    html = (static / "index.html").read_text(encoding="utf-8")
    for needle in (
        "ATLAS_UNIVERSE",
        "startRepositoryTour",
        "exportGraphPNG",
        "exportGraphSVG",
        "moduleInspector",
        "System Health",
        "timelinePanel",
    ):
        assert needle in app or needle in universe or needle in html, needle
    assert "linkDirectionalParticles" in universe
    assert "FogExp2" in universe


def test_svg_export_topology_from_galaxy_layout(scanned):
    graph = api.current_graph("module")
    xs = [n["galaxy_x"] for n in graph["nodes"]]
    ys = [n["galaxy_y"] for n in graph["nodes"]]
    assert len(xs) == graph["node_count"]
    assert max(xs) - min(xs) > 10
    assert max(ys) - min(ys) > 10


def test_product_repo_graph_scale_unchanged():
    repo_root = Path(__file__).resolve().parents[2]
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    scan = api.scan_repository(str(repo_root))
    assert scan["ok"]
    graph = api.current_graph("module")
    assert graph["node_count"] == scan["module_count"] or graph["node_count"] <= api.GRAPH_DISPLAY_CAP
    assert graph["total_edges"] == scan["dependency_edges"]
    assert graph["layout"] == "galaxy"
