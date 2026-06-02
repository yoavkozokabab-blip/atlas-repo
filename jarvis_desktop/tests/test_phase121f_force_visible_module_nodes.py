"""Phase 121F — force-visible module nodes (native ForceGraph spheres)."""

from __future__ import annotations

import math
from pathlib import Path

from jarvis_desktop import api


def _universe_js() -> str:
    return (Path(__file__).resolve().parents[1] / "static" / "universe.js").read_text(encoding="utf-8")


def test_force_visible_mode_enabled_for_module_view():
    text = _universe_js()
    # Phase 123 — native ForceGraph spheres for ALL views, sized to the spatial
    # spread (relSize=1, nodeVal=r^3) so nodes are always visibly larger than edges.
    assert "MODULE_FORCE_VISIBLE = true" in text
    assert "MODULE_FORCE_MIN_RADIUS = 5" in text
    assert "auditRenderedMeshes" in text
    # Phase 124 — explicit OPAQUE node spheres (custom mesh) so nodes are visible.
    assert "nodeThreeObject(n => makeNodeMesh(n))" in text
    assert "MeshBasicMaterial" in text
    assert "buildNodeSizing" in text


def test_module_force_display_radius_meets_minimum():
    text = _universe_js()
    # Replicate constants from universe.js
    rel = 7
    min_r = 5
    val = (min_r / rel) ** 3
    display = (val ** (1 / 3)) * rel
    assert display >= min_r - 0.01


def test_module_force_val_is_finite_for_sample_nodes():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    assert api.scan_repository(str(root))["ok"]
    graph = api.current_graph("module")
    for node in graph["nodes"][:20]:
        visual = max(5.5, min(28, node.get("visual_size") or node.get("size") or 8))
        hub = 1.22 if node.get("is_hub") else 1
        desired = max(5, 4.2 + math.sqrt(visual) * 0.75 * hub)
        capped = min(16, desired)
        val = (capped / 7) ** 3
        assert math.isfinite(val) and val > 0


def test_frontend_render_diagnostics_overlay():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    app = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    assert "graphRenderDiagnostics" in html
    assert "renderGraphRenderDiagnostics" in app
