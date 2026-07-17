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


def test_first_run_tour_is_a_stepper():
    # 4 steps, progress indicator, Back/Next/Skip, reopenable, Esc hint.
    assert 'data-onboard-step="0"' in INDEX
    assert 'data-onboard-step="3"' in INDEX
    assert 'id="onboardStepLabel"' in INDEX
    assert "Skip tour" in INDEX
    assert 'id="onboardBackBtn"' in INDEX and 'id="onboardNextBtn"' in INDEX
    assert "Reopen welcome tour" in INDEX
    assert "reopenOnboarding" in APP
    assert "onboardingRunImpact" in APP
    # Keyboard support: Escape closes the tour.
    assert '"Escape"' in APP


def test_home_primary_cta_is_analyze_impact():
    assert 'onclick="go(\'impact\')">Analyze impact</button>' in INDEX
    # Ask stays available but not as the primary header action.
    head = INDEX.split('class="repo-command-actions"', 1)[1][:400]
    assert head.count("btn primary") == 1


def test_workflows_have_distinct_placeholders():
    assert "Ask a question" in INDEX  # Ask
    assert "Add user authentication" in INDEX  # Plan example
    assert "fail intermittently" in INDEX  # Debug example
    assert "or pick from scanned files below" in INDEX  # Impact


def test_sidebar_agent_chip_never_overstates_connection():
    # Template literals: `${n} agent(s) connected` only for verified handshakes,
    # otherwise `${n} agent(s) configured`.
    assert '"} connected`' in WORKBENCH
    assert '"} configured`' in WORKBENCH
    assert 'agentVerificationState(key, agents?.[key]) === "verified"' in WORKBENCH
