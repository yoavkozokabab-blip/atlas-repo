"""Phase 124 — Repository Map visual fix.

Asserts the rendering contract (global THREE + opaque custom-mesh node spheres)
and the clean layout (no floating center badge, debug overlay hidden by default,
compact banners, module list + inspector empty state present).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
APP = (STATIC / "app.js").read_text(encoding="utf-8")
UNIVERSE = (STATIC / "universe.js").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Node visibility contract (the critical fix)
# --------------------------------------------------------------------------

class TestNodeVisibilityContract:
    def test_global_three_script_present(self):
        # Without a global THREE, custom node meshes never render (the root cause).
        # RC-1 vendors three.js locally (no CDN — local-first, works offline).
        assert 'src="vendor/three.min.js"' in INDEX
        # THREE must load before 3d-force-graph / app scripts.
        assert INDEX.index("three.min.js") < INDEX.index("3d-force-graph")

    def test_opaque_custom_mesh_path(self):
        assert "nodeThreeObject(n => makeNodeMesh(n))" in UNIVERSE
        assert "function makeNodeMesh" in UNIVERSE

    def test_node_material_is_opaque_and_unlit(self):
        # MeshBasicMaterial is unlit (always bright); fog:false stops fading.
        block = UNIVERSE[UNIVERSE.index("function makeNodeMesh"):]
        block = block[: block.index("function refreshNodeMeshColors")]
        assert "MeshBasicMaterial" in block
        assert "transparent: false" in block
        assert "fog: false" in block

    def test_risk_and_cycle_coloring(self):
        block = UNIVERSE[UNIVERSE.index("function baseNodeColorHex"):]
        block = block[: block.index("function makeNodeMesh")]
        # RC-1 calm palette (646bceac): softer indigo/rose/amber.
        assert "in_cycle" in block          # cycle nodes
        assert "0x8B9DFF" in block          # indigo — cycle member
        assert "0xE5687A" in block          # rose — highest risk
        assert "0xD6A23B" in block          # amber — elevated risk

    def test_selection_and_hover_highlight(self):
        assert "function refreshNodeMeshColors" in UNIVERSE
        assert "refreshNodeMeshColors()" in UNIVERSE  # called from syncHighlightVisuals

    def test_fog_reduced(self):
        # Heavy fog hid the graph; a very light density is kept, tinted to the
        # calm background color.
        assert "FogExp2(0x0B0F14, 0.00035)" in UNIVERSE


# --------------------------------------------------------------------------
# Clean layout (no overlapping clutter)
# --------------------------------------------------------------------------

class TestCleanLayout:
    def test_flow_header_exists(self):
        assert 'class="map-header"' in INDEX
        assert 'class="map-titlebar"' in INDEX
        assert 'class="map-metrics' in INDEX

    def test_repo_name_and_health_badge_in_header(self):
        assert 'id="mapRepoName"' in INDEX
        assert 'id="mapHealthBadge"' in INDEX

    def test_center_mode_badge_hidden(self):
        # The floating "MODULE GRAPH" badge must not show in normal view.
        assert ".graph-mode-badge{display:none!important}" in CSS
        assert 'badge.style.display = "none"' in APP

    def test_debug_overlay_hidden_by_default(self):
        assert "ATLAS_SHOW_GRAPH_DEBUG = false" in APP

    def test_advanced_toolbar_groups_decorative_actions(self):
        # PNG / SVG / Screenshot / Tour live under Advanced. The demo-bundle
        # export was removed in RC-1 with the other beta-era actions.
        adv = INDEX[INDEX.index("graph-advanced-toolbar"):]
        adv = adv[: adv.index("</details>")]
        for action in ("exportGraphPNG", "exportGraphSVG",
                       "toggleScreenshotMode", "startRepositoryTour"):
            assert action in adv, f"{action} should be under Advanced"
        assert "exportDemoBundle" not in INDEX

    def test_concise_warning_with_details(self):
        assert "Some file links could not be resolved. Most missing links are external or dynamic imports." in APP
        assert "map-warning-details" in CSS

    def test_compact_massive_banner(self):
        assert 'class="map-massive"' in INDEX
        # Massive 'show full graph' button hidden when already on module view.
        assert 'onModule ? "none" : "inline-block"' in APP

    def test_graph_fills_remaining_space(self):
        assert "#graph3d{flex:1 1 auto;min-height:0;width:100%}" in CSS


# --------------------------------------------------------------------------
# Module list + inspector
# --------------------------------------------------------------------------

class TestModuleListAndInspector:
    def test_module_list_present(self):
        assert 'id="moduleBrowsePanel"' in INDEX
        assert "function filterModuleBrowseList" in APP

    def test_module_list_has_required_columns(self):
        block = APP[APP.index("function filterModuleBrowseList"):]
        block = block[: block.index("function selectModuleFromList")]
        # path, risk, fan-in, fan-out, subsystem
        assert "mbp-path" in block
        assert "risk " in block
        # RC-1 uses plain-language counts instead of in/out jargon.
        assert "${fi} dependents" in block and "${fo} imports" in block
        assert "n.subsystem" in block

    def test_selecting_module_updates_inspector(self):
        block = APP[APP.index("function selectModuleFromList"):]
        block = block[: block.index("\n}", block.index("function selectModuleFromList")) + 2]
        assert "showNode(node)" in block

    def test_inspector_empty_state(self):
        ph = APP[APP.index("function renderModuleInspectorPlaceholder"):]
        ph = ph[: ph.index("function inspectorSearchModules")]
        assert "Select a module" in ph
        assert "inspectorSearch" in ph        # search input
        assert "Top hubs" in ph
        assert "Top risks" in ph
