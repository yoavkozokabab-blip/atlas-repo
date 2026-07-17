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


def test_connected_requires_live_runtime_state():
    # Behavior contract: "Connected" is derived exclusively from live backend
    # connection state (data.connected / connections.clients[...].connected),
    # never from configuration alone and never from a written-config fallback
    # heuristic (last_handshake timestamps, config-file existence, etc.).
    for src in (WORKBENCH, SHELL):
        assert 'data?.connected || data?.connection?.connected' in src
        assert '"connected"' in src
    # The primary label flips only on that live state.
    assert 'connected ? "Connected" : "Not connected"' in WORKBENCH
    # Configuration alone must never yield the Connected label anywhere.
    for src, name in ((WORKBENCH, "workbench"), (MCP, "mcp_setup"), (SHELL, "shell")):
        assert 'atlas_configured ? "Connected"' not in src, name
        assert 'configured ? "Connected"' not in src, name
    # No stale-heuristic fallback may exist in the connected derivation.
    assert "last_handshake" not in WORKBENCH
    assert "mcp_handshake_ok" not in WORKBENCH
    # Home's connected-agents derivation must use live state, not heuristics.
    assert "data?.connected || data?.connection?.connected" in APP
    assert "last_handshake" not in APP


def test_configured_but_disconnected_shows_not_connected():
    # A configured client without a live connection reads "Not connected"
    # plus an explicit restart instruction — config must not read as success.
    assert "MCP configuration installed. Restart" in WORKBENCH
    assert "to connect." in WORKBENCH
    assert '"Not connected"' in WORKBENCH


def test_agents_summary_leads_with_connection():
    assert "Connected clients" in INDEX
    # The summary count comes from the live connected list, not the
    # configured list.
    assert "Connected clients: ${connected.length}" in SHELL
    assert "Configured clients: ${configured.length}" in SHELL


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
    assert 'agentVerificationState(key, agents?.[key]) === "connected"' in WORKBENCH
    # The stale "verified" comparison would never match the refactored state
    # machine and silently understate live connections.
    assert '=== "verified"' not in WORKBENCH


ACCOUNTS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")


def test_account_chip_states_are_unambiguous():
    # guest -> "Guest"; pre-login -> "Sign in" (an action, not a status);
    # signed-in -> username plus plan title (Free/Pro). Never a bare
    # ambiguous "Account" status chip.
    assert "chip.textContent = 'Guest'" in ACCOUNTS
    assert "chip.textContent = 'Sign in'" in ACCOUNTS
    assert "chip.textContent = 'Account'" not in ACCOUNTS
    assert "plan === 'pro' ? 'Pro' : 'Free'" in ACCOUNTS
    assert "${planTitle}" in ACCOUNTS
