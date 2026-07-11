"""Phase 119 — Atlas desktop product polish tests.

Covers:
- Atlas branding on main page (title, logo text)
- All API routes are registered (no missing endpoints)
- Scan success UI payload fields
- Partial graph warning in summary
- Export copy payload
- Copilot fallback behaviour
- Graph mode switching state
- Module inspector fields
- Bug hunt fallback
- Home screen copy elements
"""

from __future__ import annotations

import os
import re
import sys

import pytest

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from atlas_desktop import server


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

pytestmark = pytest.mark.usefixtures("local_guest_account")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _dispatch(method, path, body=None, query=None):
    return server.dispatch(method, path, body, query)


def _html() -> str:
    with open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8") as fh:
        return fh.read()


def _js() -> str:
    with open(os.path.join(STATIC_DIR, "app.js"), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Atlas branding
# --------------------------------------------------------------------------

class TestAtlasBranding:
    def test_title_says_atlas(self):
        html = _html()
        assert "<title>ATLAS" in html, "Page title should start with ATLAS"

    def test_logo_text_is_atlas(self):
        html = _html()
        assert 'class="logo-text">ATLAS<' in html, "Logo text should be ATLAS"

    def test_hero_title_is_atlas(self):
        # Launch UI: the hero is the launch-hero header; branding lives in the topbar logo.
        html = _html()
        assert 'class="launch-hero' in html, "Launch hero header should be present"

    def test_no_jarvis_in_title(self):
        html = _html()
        assert "JARVIS" not in html.split("<title>")[1].split("</title>")[0]

    def test_onboarding_says_atlas(self):
        # Launch first-run hero headline.
        html = _html()
        assert "Give Claude Code and Cursor repo memory" in html

    def test_presentation_badge_says_atlas(self):
        html = _html()
        assert "ATLAS · Repository Intelligence" in html

    def test_hero_headline_present(self):
        html = _html()
        assert "Give Claude Code and Cursor repo memory" in html

    def test_hero_subheadline_present(self):
        html = _html()
        assert "answers repo-aware questions with cited files" in html

    def test_steps_row_present(self):
        # Launch home shows the no-repo actions and the HN demo entry.
        html = _html()
        assert "Load sample repository" in html
        assert "Scan local repository" in html
        assert "HN demo" in html

    def test_home_actions_present(self):
        # RC-1 first-run Home shows exactly two actions: scan or load the sample.
        html = _html()
        assert "Scan local repository" in html
        assert "Load sample repository" in html

    def test_js_uses_atlas_keys(self):
        js = _js()
        assert 'atlas_recent_repos' in js
        assert 'atlas_onboarding_v2_done' in js

    def test_js_export_filename_atlas(self):
        js = _js()
        assert 'atlas_context_' in js
        assert 'atlas-universe-' in js

    def test_js_demo_load_message_atlas(self):
        js = _js()
        assert "Loading Atlas demo" in js

    def test_server_version_atlas(self):
        assert "AtlasDesktop" in server.AtlasHandler.server_version


# --------------------------------------------------------------------------
# API route health (no missing endpoints)
# --------------------------------------------------------------------------

EXPECTED_ROUTES = [
    ("GET", "/api/health"),
    ("POST", "/api/system/browse-folder"),
    ("POST", "/api/repositories/select"),
    ("POST", "/api/repositories/validate"),
    ("POST", "/api/repositories/estimate"),
    ("POST", "/api/demo/load"),
    ("GET", "/api/demo/packs"),
    ("POST", "/api/demo/export-bundle"),
    ("POST", "/api/analytics/event"),
    ("GET", "/api/analytics/summary"),
    ("POST", "/api/repositories/scan"),
    ("GET", "/api/repositories/current/scan-status"),
    ("POST", "/api/repositories/current/cancel-scan"),
    ("GET", "/api/repositories/current/summary"),
    ("GET", "/api/repositories/current/graph"),
    ("GET", "/api/repositories/current/hierarchy-graph"),
    ("GET", "/api/repositories/current/timeline"),
    ("GET", "/api/repositories/current/tour"),
    ("GET", "/api/repositories/current/module"),
    ("GET", "/api/repositories/current/risks"),
    ("POST", "/api/impact"),
    ("POST", "/api/planning/change"),
    ("POST", "/api/planning/investigate"),
    ("POST", "/api/planning/impact"),
    ("POST", "/api/bug-investigation"),
    ("POST", "/api/context/export"),
    ("POST", "/api/copilot/ask"),
]


class TestRouteHealth:
    @pytest.mark.parametrize("method,path", EXPECTED_ROUTES)
    def test_route_registered(self, method, path):
        assert server.route_is_registered(method, path), \
            f"Route not registered: {method} {path}"

    def test_unknown_route_returns_404(self):
        status, payload = _dispatch("GET", "/api/nonexistent")
        assert status == 404
        assert not payload["ok"]

    def test_unknown_route_error_not_raw_exception(self):
        status, payload = _dispatch("GET", "/api/does-not-exist")
        assert payload.get("error", "").startswith("Unknown endpoint")


# --------------------------------------------------------------------------
# Health endpoint
# --------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self):
        status, payload = _dispatch("GET", "/api/health")
        assert status == 200
        assert payload.get("ok") is True

    def test_health_has_version(self):
        _, payload = _dispatch("GET", "/api/health")
        assert "version" in payload

    def test_health_repository_open_field(self):
        _, payload = _dispatch("GET", "/api/health")
        assert "repository_open" in payload


# --------------------------------------------------------------------------
# Repository validation
# --------------------------------------------------------------------------

class TestRepositoryValidation:
    def test_empty_path_fails(self):
        _, payload = _dispatch("POST", "/api/repositories/validate", {"path": ""})
        assert not payload.get("ok")

    def test_nonexistent_path_fails(self):
        _, payload = _dispatch("POST", "/api/repositories/validate",
                               {"path": r"C:\does\not\exist\at\all"})
        assert not payload.get("ok")
        assert "error" in payload

    def test_error_message_is_user_friendly(self):
        _, payload = _dispatch("POST", "/api/repositories/validate",
                               {"path": r"C:\does\not\exist"})
        error = payload.get("error", "")
        assert error
        assert "Unknown endpoint" not in error


# --------------------------------------------------------------------------
# Scan success UI payload fields
# --------------------------------------------------------------------------

class TestScanSuccessPayload:
    """Tests that the scan endpoint returns fields the UI requires to render
    the success summary."""

    REQUIRED_FIELDS = [
        "ok", "repo_name", "scan_duration_seconds", "file_count",
        "module_count", "dependency_edges", "subsystem_count",
    ]

    def test_demo_scan_has_required_fields(self):
        _, scan = _dispatch("POST", "/api/demo/load", {"pack": "small"})
        assert scan.get("ok"), f"Demo load failed: {scan.get('error')}"
        for field in self.REQUIRED_FIELDS:
            assert field in scan, f"scan payload missing: {field}"

    def test_demo_scan_numeric_fields(self):
        _, scan = _dispatch("POST", "/api/demo/load", {"pack": "small"})
        assert scan.get("ok")
        assert isinstance(scan.get("module_count"), int)
        assert isinstance(scan.get("dependency_edges"), int)

    def test_scan_duration_non_negative(self):
        _, scan = _dispatch("POST", "/api/demo/load", {"pack": "small"})
        assert scan.get("ok")
        assert (scan.get("scan_duration_seconds") or 0) >= 0


# --------------------------------------------------------------------------
# Partial graph warning
# --------------------------------------------------------------------------

class TestPartialGraphWarning:
    def test_summary_has_graph_health(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})
        _, summary = _dispatch("GET", "/api/repositories/current/summary")
        assert summary.get("ok")
        gh = summary.get("graph_health", {})
        assert "label" in gh

    def test_graph_health_label_is_string(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})
        _, summary = _dispatch("GET", "/api/repositories/current/summary")
        label = summary.get("graph_health", {}).get("label", "")
        assert isinstance(label, str)
        assert label  # not empty

    def test_graph_health_notice_field_exists(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})
        _, summary = _dispatch("GET", "/api/repositories/current/summary")
        gh = summary.get("graph_health", {})
        # notice is optional but must be absent or a string
        assert gh.get("notice") is None or isinstance(gh.get("notice"), str)


# --------------------------------------------------------------------------
# AI Export copy payload
# --------------------------------------------------------------------------

class TestExportCopyPayload:
    def _load_demo(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})

    def test_export_claude_compact(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/context/export",
                           {"target": "claude", "packet": "compact"})
        assert res.get("ok")
        assert res.get("text")
        assert isinstance(res.get("estimated_tokens"), int)

    def test_export_codex_compact(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/context/export",
                           {"target": "codex", "packet": "compact"})
        assert res.get("ok")
        assert res.get("text")

    def test_export_verbose_longer_than_compact(self):
        self._load_demo()
        _, compact = _dispatch("POST", "/api/context/export",
                               {"target": "claude", "packet": "compact"})
        _, verbose = _dispatch("POST", "/api/context/export",
                               {"target": "claude", "packet": "verbose"})
        assert compact.get("ok") and verbose.get("ok")
        assert len(verbose.get("text", "")) >= len(compact.get("text", ""))

    def test_export_target_and_packet_in_response(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/context/export",
                           {"target": "cursor", "packet": "compact"})
        assert res.get("ok")
        assert res.get("target") == "cursor"
        assert res.get("packet") == "compact"

    def test_export_no_scan_fails_gracefully(self):
        # Reset state by loading nothing; just check the response is not a raw 500
        from atlas_desktop import api as dapi
        dapi._STATE["scan"] = None
        dapi._STATE["path"] = None
        _, res = _dispatch("POST", "/api/context/export",
                           {"target": "claude", "packet": "compact"})
        assert "ok" in res  # must be a structured response
        if not res.get("ok"):
            assert res.get("error")


# --------------------------------------------------------------------------
# Copilot fallback
# --------------------------------------------------------------------------

class TestCopilotFallback:
    def _load_demo(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})

    def test_copilot_answer_present(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/copilot/ask",
                           {"question": "What does this repo do?", "target": "none", "packet": "compact"})
        assert res.get("ok")
        assert res.get("answer")

    def test_copilot_has_confidence(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/copilot/ask",
                           {"question": "What are the top risks?", "target": "none", "packet": "compact"})
        assert res.get("ok")
        assert res.get("confidence") in {"high", "medium", "low", "unknown", None}

    def test_copilot_no_repo_returns_error(self):
        from atlas_desktop import api as dapi
        dapi._STATE["scan"] = None
        dapi._STATE["path"] = None
        _, res = _dispatch("POST", "/api/copilot/ask",
                           {"question": "What does this do?", "target": "none", "packet": "compact"})
        assert not res.get("ok")
        assert res.get("error")

    def test_copilot_no_repo_error_is_user_friendly(self):
        from atlas_desktop import api as dapi
        dapi._STATE["scan"] = None
        dapi._STATE["path"] = None
        _, res = _dispatch("POST", "/api/copilot/ask",
                           {"question": "Anything", "target": "none", "packet": "compact"})
        error = res.get("error", "")
        assert "Unknown endpoint" not in error
        # Should not be a raw Python traceback
        assert "Traceback" not in error

    def test_copilot_returns_evidence_list(self):
        self._load_demo()
        _, res = _dispatch("POST", "/api/copilot/ask",
                           {"question": "What are the top architectural risks?",
                            "target": "none", "packet": "compact"})
        if res.get("ok"):
            assert isinstance(res.get("evidence"), list)


# --------------------------------------------------------------------------
# Graph mode switching state
# --------------------------------------------------------------------------

class TestGraphModeSwitching:
    def _load_demo(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})

    def test_module_graph_ok(self):
        self._load_demo()
        _, graph = _dispatch("GET", "/api/repositories/current/graph", query={"view": "module"})
        assert graph.get("ok")
        assert isinstance(graph.get("nodes"), list)
        assert isinstance(graph.get("links"), list)

    def test_subsystem_graph_ok(self):
        self._load_demo()
        _, graph = _dispatch("GET", "/api/repositories/current/graph", query={"view": "subsystem"})
        assert graph.get("ok")
        assert isinstance(graph.get("nodes"), list)

    def test_hierarchy_graph_subsystem_level(self):
        self._load_demo()
        _, graph = _dispatch("GET", "/api/repositories/current/hierarchy-graph",
                             query={"level": "subsystem", "parent": ""})
        assert graph.get("ok")

    def test_graph_has_node_count(self):
        self._load_demo()
        _, graph = _dispatch("GET", "/api/repositories/current/graph", query={"view": "module"})
        assert graph.get("ok")
        assert "node_count" in graph
        assert graph["node_count"] >= 0

    def test_graph_has_link_count(self):
        self._load_demo()
        _, graph = _dispatch("GET", "/api/repositories/current/graph", query={"view": "module"})
        assert graph.get("ok")
        assert "link_count" in graph


# --------------------------------------------------------------------------
# Module inspector
# --------------------------------------------------------------------------

class TestModuleInspector:
    def test_inspector_no_target_fails_gracefully(self):
        _dispatch("POST", "/api/demo/load", {"pack": "small"})
        _, res = _dispatch("GET", "/api/repositories/current/module", query={"target": ""})
        assert "ok" in res
        if not res.get("ok"):
            assert res.get("error")
            assert "Unknown endpoint" not in res.get("error", "")

    def test_inspector_has_atlas_html_structure(self):
        html = _html()
        assert 'id="moduleInspector"' in html
        assert 'id="inspectorQuick"' in html

    def test_inspector_quick_has_buttons(self):
        html = _html()
        assert "copyInspectorPath" in html
        assert "genInspectorPrompt" in html


# --------------------------------------------------------------------------
# UI structure checks (static HTML)
# --------------------------------------------------------------------------

class TestUIStructure:
    def test_investigate_bug_section_present(self):
        html = _html()
        assert 'id="view-investigate"' in html
        assert "traceback" in html.lower() or "stack trace" in html.lower()

    def test_export_why_section_present(self):
        html = _html()
        assert 'class="export-why"' in html
        assert "Advanced context export" in html

    def test_graph_legend_present(self):
        html = _html()
        assert 'id="graphLegend"' in html
        assert "Elevated risk" in html
        assert "High risk" in html

    def test_reset_view_button_present(self):
        html = _html()
        assert "resetGraphView" in html
        assert "Reset View" in html

    def test_scan_btn_disabled_by_default(self):
        html = _html()
        assert 'id="scanBtn" disabled' in html

    def test_browse_btn_has_distinct_class(self):
        html = _html()
        assert "browse-btn" in html

    def test_picker_help_references_atlas_or_local(self):
        # Picker help text should not say JARVIS
        html = _html()
        picker_help_match = re.search(r'class="picker-help">(.*?)</p>', html, re.DOTALL)
        if picker_help_match:
            assert "JARVIS" not in picker_help_match.group(1)

    def test_no_jarvis_in_user_visible_labels(self):
        html = _html()
        # Allow "JARVIS" only inside HTML comments, script src attrs, or data attributes
        # Strip comments and script content, then check
        stripped = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        stripped = re.sub(r'<script[^>]*>.*?</script>', '', stripped, flags=re.DOTALL)
        # Allow in class/id names that are internal identifiers
        text_only = re.sub(r'<[^>]+>', ' ', stripped)
        assert "JARVIS" not in text_only, \
            "User-visible text should not contain JARVIS"
