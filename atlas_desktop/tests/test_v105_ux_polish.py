"""v1.0.5 UX polish guards — MCP connection semantics + Impact result states.

These assert user-visible contract strings in the shipped frontend so a
regression to configuration-as-success or a collapsed Impact state fails CI.
"""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
APP = (STATIC / "app.js").read_text(encoding="utf-8")
WORKBENCH = (STATIC / "workbench-v3.js").read_text(encoding="utf-8")
MCP = (STATIC / "atlas_mcp_setup.js").read_text(encoding="utf-8")
SHELL = (STATIC / "desktop-shell.js").read_text(encoding="utf-8")
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")


def test_connected_requires_verified_handshake():
    # Primary badge is Connected/Not connected, driven by verification state,
    # never by configuration alone.
    assert '"Connected" : "Not connected"' in WORKBENCH
    assert 'verification === "verified" ? "Connected"' in WORKBENCH
    # A written config file must not produce a "Connected" primary label.
    assert 'configured ? "Connected"' not in WORKBENCH
    assert 'claudeOn ? "Connected"' not in MCP
    assert 'cursorOn ? "Connected"' not in MCP
    assert 'codexOn ? "Connected"' not in MCP


def test_configured_state_gives_restart_instruction():
    assert "MCP configuration installed. Restart" in WORKBENCH
    assert "to connect." in WORKBENCH


def test_agents_summary_leads_with_connection():
    assert "Connected clients" in INDEX
    assert "Connected clients: ${verified.length}" in SHELL


def test_impact_has_distinct_visible_states():
    # loading / not-found / failed / success are separate surfaces.
    assert "impact-loading" in APP
    assert "impact-state-not-found" in APP
    assert "impact-state-failed" in APP
    assert "Target not found in this repository" in APP
    assert "No indexed dependents found." in APP
