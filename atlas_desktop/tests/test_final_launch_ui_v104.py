"""Focused regression tests for Atlas v1.0.4 launch hotfix."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from atlas_desktop import product_info

STATIC = Path(__file__).resolve().parents[1] / "static"
APP = STATIC / "app.js"
INDEX = STATIC / "index.html"
SHELL = STATIC / "desktop-shell.js"
WORKBENCH = STATIC / "workbench-v3.js"
MCP = STATIC / "atlas_mcp_setup.js"
PRODUCT = STATIC / "atlas_product.js"
CSS = STATIC / "ui-polish-v104.css"


def _run_node(script: str) -> dict:
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for deterministic frontend hotfix tests")
    with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    try:
        proc = subprocess.run(
            [node, path],
            capture_output=True,
            text=True,
            check=False,
            timeout=45,
        )
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        pytest.fail(proc.stderr or proc.stdout or "node script failed")
    return json.loads(proc.stdout.strip())


def test_product_version_matches_the_release_identity():
    assert product_info.PRODUCT_VERSION == "1.0.6-beta.2"
    assert product_info.LAUNCH_BUILD_LABEL == "Atlas v1.0.6-beta.2"


def test_footer_and_settings_hide_public_build_hash():
    html = INDEX.read_text(encoding="utf-8")
    assert f"Atlas {product_info.PRODUCT_VERSION}" in html
    assert "ui-polish-v104.css" in html
    assert "settingsAdvancedFacts" in html
    assert "Build commit" not in html
    product_js = PRODUCT.read_text(encoding="utf-8")
    assert "build_commit" not in product_js.split("atlasFormatVersionLine", 1)[1][:400]
    shell = SHELL.read_text(encoding="utf-8")
    assert '["Build commit", product && product.build_commit]' not in shell


def test_diagnostic_grid_has_five_columns_without_blank_cell_layout():
    css = CSS.read_text(encoding="utf-8")
    redesign = (STATIC / "desktop-redesign.css").read_text(encoding="utf-8")
    assert "repeat(5, minmax(0, 1fr))" in css or "repeat(5, minmax(0, 1fr))" in redesign
    assert "diagnostic-action-grid.is-healthy" in css


def test_agents_verification_semantics():
    mcp = MCP.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    assert 'codexOn ? "Codex configured"' not in mcp
    assert '"Codex configured"' not in mcp.split("setText(")[1:]
    assert "connectionFor" in mcp
    assert 'connected ? "Connected" : "Not connected"' in mcp
    assert 'if (key === "cursor") return "verified"' not in shell


def test_repository_switch_clears_workflow_context():
    app = APP.read_text(encoding="utf-8")
    assert "function clearWorkflowInvestigationState" in app
    assert 'document.addEventListener("atlas:repository-invalidated", (event) => {' in app
    assert 'if (event?.detail?.reason === "history") return;' in app
    assert "clearWorkflowInvestigationState();" in app
    # The impact renderer must not call Array methods on a Set (v1.0.4 rc bug:
    # `new Set(...).filter(...)` threw and left the Impact panel permanently empty).
    assert ".filter is not a function" not in app
    assert "]).filter(Boolean)].slice" not in app
    assert "STATE.impactResult = null" in app
    assert "renderWorkflowContextLine(view)" in app
    assert "workflow-empty-state" in app


def test_home_activity_scopes_to_active_repository():
    workbench_source = WORKBENCH.read_text(encoding="utf-8")
    assert "scopedHistory" in workbench_source
    assert "scopedRecent" in workbench_source


def test_scroll_reset_helpers_present():
    app = APP.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "function resetViewScroll" in app
    assert "function atlasScrollContainer" in app
    assert "overflow: hidden" in css
    assert "overflow-y: auto" in css


def test_impact_result_visible_without_advanced_only_wrapper():
    app = APP.read_text(encoding="utf-8")
    assert "No indexed dependents found." in app
    assert 'class="impact-result-panel glass ocard impact-card"' in app
    assert "advanced-only glass ocard impact-card" not in app
