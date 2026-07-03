"""Phase 121E — module node world-scale rendering (ForceGraph3D)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas_desktop import api


def _universe_js() -> str:
    return (Path(__file__).resolve().parents[1] / "static" / "universe.js").read_text(encoding="utf-8")


def test_sphere_node_object_never_returns_null_for_valid_node():
    text = _universe_js()
    body = text[text.find("function sphereNodeObject") : text.find("function setupScene")]
    assert "if (!node?.id) return null" in body
    assert "if (!Number.isFinite(scale) || scale <= 0) return null" in body
    assert "transparent: false" in body
    assert "MODULE_MIN_RADIUS" in text


def test_module_force_visible_path_for_module_graph():
    text = _universe_js()
    # Phase 124 — explicit opaque custom-mesh spheres, bounds-aware sizing.
    assert "MODULE_FORCE_VISIBLE" in text
    assert "nativeDisplayRadius" in text
    assert "nodeThreeObject(n => makeNodeMesh(n))" in text


def test_node_val_branch_for_native_sphere_mode():
    text = _universe_js()
    build = text[text.find("function buildGraph") : text.find("function getBlastState")]
    # Phase 123 — single native-sphere path: bounds-aware sizing applied to all views.
    assert "nativeNodeVal" in build
    assert "buildNodeSizing" in build


def test_hover_path_unchanged():
    text = _universe_js()
    assert "scheduleHoverUpdate" in text
    assert "U.lastHoverId" in text
    assert "graphData(" not in text[text.find("function scheduleHoverUpdate") : text.find("function applySelectionHighlight")]


@pytest.fixture()
def scanned_ts_repo():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


def test_module_payload_sizes_are_finite_and_bounded(scanned_ts_repo):
    graph = api.current_graph("module")
    assert graph["ok"] and graph["nodes"]
    for node in graph["nodes"]:
        assert node["visual_size"] >= api.MODULE_VISUAL_SIZE_MIN
        assert node["size"] <= api.MODULE_VISUAL_SIZE_MAX


def test_galaxy_positions_span_larger_than_old_mesh_radius():
    graph = api.current_graph("module")
    xs = [n["galaxy_x"] for n in graph["nodes"]]
    span = max(xs) - min(xs)
    old_max_radius = 0.36 * (api.MODULE_VISUAL_SIZE_MAX ** 0.5)
    assert span > old_max_radius * 20, "layout span must dwarf legacy mesh radii"
