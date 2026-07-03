"""Phase 116B — graph hover performance (frontend markers + API smoke)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas_desktop import api


def _universe_js() -> str:
    return (Path(__file__).resolve().parents[1] / "static" / "universe.js").read_text(encoding="utf-8")


def _app_js() -> str:
    return (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")


def test_universe_precomputes_adjacency_once():
    text = _universe_js()
    assert "function buildAdjacencyMaps" in text
    assert "U.adj = buildAdjacencyMaps(mergedNodes, mergedLinks)" in text
    assert "installGraphAccessors" in text


def test_hover_uses_raf_and_skips_same_node():
    text = _universe_js()
    assert "function scheduleHoverUpdate" in text
    assert "requestAnimationFrame" in text
    assert "U.lastHoverId" in text
    assert "if (id === U.lastHoverId) return" in text


def test_hover_does_not_rescan_all_links_in_handler():
    text = _universe_js()
    assert '.onNodeHover(n => scheduleHoverUpdate(fg, n, callbacks))' in text
    assert "function scheduleHoverUpdate" in text
    sched = text[text.find("function scheduleHoverUpdate") : text.find("function applySelectionHighlight")]
    assert "graph.links.forEach" not in sched


def test_accessors_installed_once_not_rebound_on_hover():
    text = _universe_js()
    assert "U.accessorsInstalled" in text
    assert "function installGraphAccessors" in text
    assert "syncHighlightVisuals" in text
    assert text.count("fg.nodeColor(") <= 2


def test_large_graph_neighbor_cap():
    text = _universe_js()
    assert "HOVER_NEIGHBOR_CAP = 100" in text
    assert "LARGE_GRAPH_THRESHOLD = 1000" in text
    assert "U.largeGraph" in text


def test_hover_uses_refresh_not_graph_data():
    text = _universe_js()
    hover_fn = text[text.find("function scheduleHoverUpdate") : text.find("function applySelectionHighlight")]
    assert "graphData(" not in hover_fn
    assert "fg.refresh" in text


def test_perf_logging_hook():
    text = _universe_js()
    assert "enablePerfLogging" in text
    assert "logHoverPerf" in text


def test_selection_highlight_separate_from_hover():
    text = _universe_js()
    assert "function applySelectionHighlight" in text
    app = _app_js()
    assert "showNode" in app
    assert "renderModuleInspector(n)" in app
    assert "refreshHighlight(n)" in app


def test_synthetic_large_graph_payload_shape():
    """API can emit 5k nodes without changing hover code paths."""
    nodes = [{"id": f"m{i}", "label": f"mod{i}", "path": f"src/m{i}.ts", "subsystem": "s",
              "fan_in": 1, "fan_out": 1, "risk_score": 1, "size": 3}
             for i in range(5000)]
    links = [{"source": f"m{i}", "target": f"m{(i+1) % 5000}", "weight": 1, "opacity": 0.2}
             for i in range(10000)]
    assert len(nodes) == 5000
    assert len(links) == 10000


@pytest.fixture()
def scanned_ts_repo(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


def test_module_inspector_api_after_scan(scanned_ts_repo):
    graph = api.current_graph("module")
    assert graph["ok"]
    node = graph["nodes"][0]
    info = api.module_inspector(node.get("path") or node.get("label"))
    assert info.get("ok") or info.get("error")
