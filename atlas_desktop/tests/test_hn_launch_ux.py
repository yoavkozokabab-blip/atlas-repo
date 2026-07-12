"""Hacker News launch UX contract.

A new developer should be able to load the sample, land on Ask Atlas, and ask a
repo-aware question without discovering older context/export workflows first.
"""

from __future__ import annotations

import re
from pathlib import Path

from atlas_desktop import api


STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
FIRST_QUESTION = "Where is authentication implemented?"
HN_QUESTION = "What breaks if I change services/auth.py?"


def _section(view: str) -> str:
    marker = f'id="view-{view}"'
    start = INDEX.find(marker)
    assert start >= 0, view
    end = INDEX.find("<!-- =====================", start + len(marker))
    return INDEX[start:] if end < 0 else INDEX[start:end]


def test_primary_nav_matches_launch_order_and_hides_context_export():
    nav = INDEX[INDEX.find('<nav class="nav"'): INDEX.find("</nav>", INDEX.find('<nav class="nav"'))]
    labels = re.findall(r'data-view="([^"]+)".*?>([^<]+)</button>', nav)
    assert labels == [
        ("home", "Home"),
        ("scan", "Scan"),
        ("hn", "HN demo"),
        ("ask", "Ask"),
        ("investigate", "Debug"),
        ("impact", "Impact"),
        ("build", "Plan"),
        ("center", "Map"),
    ]
    assert "Repository Context" not in nav
    assert 'class="needs-no-repo"' in nav
    assert 'class="needs-repo"' in nav


def test_home_points_to_scan_and_sample_without_full_scan_form():
    home = _section("home")
    assert "Give Claude Code and Cursor repo memory" in home
    assert "Scan a repository. Atlas builds a local map" in home
    assert "Scan local repository" in home
    assert "Load sample repository" in home
    assert "HN demo" in home
    assert 'id="repoPath"' not in home
    assert 'id="scanBtn"' not in home
    assert 'class="action-cards"' in home


def test_hn_demo_page_exists():
    hn = _section("hn")
    assert "Try Atlas in 30 seconds" in hn
    assert "Load sample repository" in hn
    assert "startHnDemo" in hn
    assert "Inspect evidence" in hn
    assert "function startHnDemo" in APP_JS


def test_scan_is_repository_loading_surface():
    scan = _section("scan")
    for marker in ('id="repoPath"', 'id="browseRepoBtn"', 'id="scanBtn"', 'id="recentList"', 'id="scanPicker"'):
        assert marker in scan
    assert "Scan a repository" in scan
    assert "Recent repositories" in scan


def test_ask_atlas_page_has_real_prompt_flow_and_empty_state():
    ask = _section("ask")
    assert 'id="askInput"' in ask
    assert "Investigation brief" in ask
    assert 'id="copilotEvidence"' in ask
    assert 'id="copilotFiles"' in ask
    for prompt in (
        FIRST_QUESTION,
        HN_QUESTION,
        "Explain the request flow.",
        "Which files should I read first?",
        "What does this repository do?",
    ):
        assert prompt in APP_JS
    assert "Atlas needs a local code map" in APP_JS
    assert "Scan a repository first" in APP_JS
    assert "data-prompt" in APP_JS
    assert "Prepare a compact context packet" not in APP_JS


def test_sample_and_real_scans_route_to_ask_atlas():
    assert "function routeToAskAfterScan" in APP_JS
    assert 'go("ask")' in APP_JS
    assert "primeAskAtlasPrompt(scan)" in APP_JS
    assert "Define an investigation or choose a template" in APP_JS


def test_sample_first_question_returns_cited_files():
    api._STATE.update({
        "path": None,
        "scan": None,
        "graph": None,
        "index": None,
        "risks": None,
        "demo_mode": False,
        "scan_cache": {},
    })
    loaded = api.load_demo_mode("medium")
    assert loaded["ok"] and loaded["demo_mode"]
    res = api.copilot_ask(HN_QUESTION)
    assert res["ok"]
    assert res["mode"] == "impact"
    assert res["confidence"] in {"medium", "high"}
    assert "services/auth.py" in (res.get("files") or [])
    assert res.get("evidence")


def test_repo_required_pages_have_useful_empty_states():
    for view, explanation in {
        "build": "Implementation planning needs indexed files",
        "investigate": "Failure investigation needs repository evidence",
        "impact": "Change impact needs a dependency graph",
    }.items():
        section = _section(view)
        assert "Scan a repository first" in section
        assert "Load sample repository" in section
        assert explanation in section
    assert "Complete a scan to render the dependency map." in APP_JS
    assert "repoRequiredEmptyHtml" in APP_JS
