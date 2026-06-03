"""Phase 121C — module graph correctness (pipeline counts, no visual changes)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jarvis_desktop import api

REPO = os.environ.get("ATLAS_TRACE_REPO", r"C:\FINAL_ALGO_TRADER")


def _count_modules(graph):
    return sum(1 for n in graph.get("nodes", []) if n.get("type") == "module")


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
            "scan_cache": {},
        }
    )
    yield


@pytest.mark.skipif(not Path(REPO).is_dir(), reason="FINAL_ALGO_TRADER not on this machine")
def test_final_algo_trader_module_payload_matches_stored_graph():
    scan = api.scan_repository(REPO, {"mode": "entire_repo"})
    assert scan["ok"], scan.get("error")
    stored = _count_modules(api._STATE["graph"])
    module = api.current_graph("module")
    overview = api.current_graph("subsystem")
    assert module["view"] == "module"
    assert module["node_count"] == stored
    assert module["node_count"] == scan["module_count"]
    assert overview["node_count"] < module["node_count"]
    assert overview.get("architecture_clusters") is True
    # Phase 133: overview may expose more than legacy ~11 clusters when subsystems are granular.
    assert overview["node_count"] <= max(20, module["node_count"] // 2)


def test_massive_mode_triggered_by_size_not_module_count():
    if not Path(REPO).is_dir():
        pytest.skip("repo missing")
    est = api.pre_scan_estimate(REPO, {"mode": "entire_repo"})
    scan = api.scan_repository(REPO, {"mode": "entire_repo"})
    reason = scan.get("massive_reason") or {}
    assert scan["module_count"] < api.MASSIVE_MODULES_THRESHOLD
    assert reason.get("size") is True or est.get("massive_mode_auto") is True


def test_hierarchy_top_level_is_subsystem_aggregate():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    assert api.scan_repository(str(root))["ok"]
    top = api.current_hierarchy_graph("subsystem")
    module = api.current_graph("module")
    assert top["node_count"] <= module["node_count"]
    assert top["total_modules"] == module["total_modules"]


def test_frontend_chunk_loader_preserves_all_module_nodes():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    assert api.scan_repository(str(root))["ok"]
    payload = api.current_graph("module")
    nodes = payload["nodes"]
    links = payload["links"]
    chunk_size = len(nodes) if len(nodes) <= 1000 else 160
    loaded = 0
    merged = []
    while loaded < len(nodes):
        chunk = nodes[loaded : loaded + chunk_size]
        loaded += len(chunk)
        merged.extend(chunk)
        ids = {n["id"] for n in merged}
        merged_links = [l for l in links if l["source"] in ids and l["target"] in ids]
    assert len(merged) == payload["node_count"]
    assert len(merged_links) == payload["link_count"]
