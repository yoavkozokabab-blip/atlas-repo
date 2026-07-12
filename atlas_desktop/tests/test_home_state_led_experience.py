"""Focused contracts for the production state-led Desktop Home."""
from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
APP = (STATIC / "app.js").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
MCP = (STATIC / "atlas_mcp_setup.js").read_text(encoding="utf-8")
WORKFLOWS = (STATIC / "atlas_workflows.js").read_text(encoding="utf-8")


def _home() -> str:
    start = INDEX.index('<section class="view active" id="view-home">')
    end = INDEX.index("<!-- ===================== HN DEMO", start)
    return INDEX[start:end]


class _IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.ids.extend(value for key, value in attrs if key == "id" and value)


def test_home_defines_three_real_state_panels_and_router() -> None:
    home = _home()
    assert home.count('data-home-panel="') == 3
    for state in ("empty", "indexed", "productive"):
        assert f'data-home-panel="{state}"' in home
    assert 'const state = !hasRepo ? "empty" : (agents.length ? "productive" : "indexed");' in APP
    assert "const hasRepo = !!summary?.ok;" in APP
    assert "atlas_configured" in APP


def test_no_repository_state_is_focused_and_uses_real_scan_handlers() -> None:
    home = _home()
    assert "Give your coding agents persistent repo context." in home
    assert "Scan once. Atlas restores the repository graph" in home
    assert 'onclick="goToScanStart()">Scan a local repository' in home
    assert 'onclick="loadDemoMode(\'medium\')">Try the sample repository' in home
    assert "No signup required" in home
    assert "mcpSetupSection" not in home[: home.index('data-home-panel="indexed"')]


def test_indexed_state_uses_reported_repository_metrics_and_freshness() -> None:
    assert 'setHomeFact("homeFileCount", fileCount)' in APP
    assert 'setHomeFact("homeNodeCount", homeMetric(summary.module_count))' in APP
    assert 'setHomeFact("homeEdgeCount", homeMetric(summary.dependency_edges))' in APP
    assert 'api("/api/repositories/recent")' in APP
    assert 'api("/api/repositories/current/trust-status")' in APP
    assert 'function setHomeFact' in APP
    assert 'el.parentElement.hidden = !visible' in APP
    assert "homeLastIndexed(summary, STATE.homeRecent)" in APP
    assert 'trustLabel === "Fresh"' in APP
    assert 'stale ? "Repository needs refresh." : "Repository ready."' in APP
    assert "Refresh before relying on graph evidence." in APP


def test_productive_home_ask_and_suggestions_route_to_existing_workspaces() -> None:
    home = _home()
    assert 'onsubmit="submitHomeAsk(event)"' in home
    assert 'if ($("askInput")) $("askInput").value = prompt;' in APP
    submit = APP[APP.index("function submitHomeAsk"): APP.index("function routeHomeSuggestion")]
    assert 'go("ask")' in submit
    assert "sendCopilotQuestion();" in submit
    for view in ("ask", "impact", "investigate", "build"):
        assert f"{view}:" in APP or f"'{view}'" in home
    for label in (
        "Find where authentication is implemented",
        "See what breaks if I change a file",
        "Trace a request across the repository",
        "Investigate an error",
        "Plan a safe change",
    ):
        assert label in home


def test_mcp_buttons_keep_real_handlers_and_advanced_actions_are_disclosed() -> None:
    home = _home()
    for tool, method in (("Claude", "connectClaude"), ("Cursor", "connectCursor"), ("Codex", "connectCodex")):
        assert f'id="mcp{tool}Btn"' in home
        assert f"atlasMcpSetup.{method}()" in home
    assert home.count('class="mcp-home-advanced"') == 3
    assert "window.renderHomeExperience({ mcpStatus: status });" in MCP
    assert '"/api/integrations/claude/write-config"' in MCP
    assert '"/api/integrations/cursor/write-config"' in MCP
    assert '"/api/integrations/codex/write-config"' in MCP


def test_guest_entry_remains_available_without_home_account_branching() -> None:
    assert "Continue without an account" in INDEX
    assert "Local-first" in _home()
    router = APP[APP.index("function renderHomeExperience"): APP.index("async function refreshHomeExperience")]
    assert "signed_in" not in router
    assert "authenticated" not in router
    assert '$("homeDashboard")?.classList.contains("atlas-home")' in WORKFLOWS
    assert "dismissWelcomeScreen(false);" in WORKFLOWS


def test_home_has_no_duplicate_ids_or_dead_inline_function_names() -> None:
    parser = _IdParser()
    parser.feed(INDEX)
    assert [item for item, count in Counter(parser.ids).items() if count > 1] == []
    handlers = re.findall(r'on(?:click|submit)="([A-Za-z_$][\w$]*)\(', _home())
    script = APP + MCP
    for handler in handlers:
        assert re.search(rf"(?:(?:async\s+)?function\s+{re.escape(handler)}\b|const\s+{re.escape(handler)}\s*=)", script), handler


def test_keyboard_focus_reduced_motion_and_minimum_width_layout() -> None:
    home = _home()
    assert 'tabindex="-1"' in home
    assert ":focus-visible" in CSS and "--atlas-focus" in CSS
    assert "prefers-reduced-motion:reduce" in CSS
    assert "@media(max-width:560px)" in CSS
    assert ".atlas-home-ask>div{grid-template-columns:1fr}" in CSS
    assert ".atlas-home-facts{grid-template-columns:1fr}" in CSS
    assert "minmax(0,1fr)" in CSS
    assert "overflow-wrap:anywhere" in CSS
