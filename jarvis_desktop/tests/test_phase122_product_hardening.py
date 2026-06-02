"""Phase 122 — Atlas product hardening: navigation, metrics honesty, grounded flows."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, planning_engine, server

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = STATIC / "index.html"
APP_JS = STATIC / "app.js"


@pytest.fixture()
def planner_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "scan_cache": {}})
    root = tmp_path / "app"
    root.mkdir()
    (root / "services").mkdir()
    (root / "services" / "live_paper_engine.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )
    (root / "services" / "backtest.py").write_text("def run_backtest():\n    return []\n", encoding="utf-8")
    (root / "ui").mkdir()
    (root / "ui" / "dashboard.py").write_text("def pnl():\n    return 0\n", encoding="utf-8")
    result = api.scan_repository(str(root))
    assert result["ok"], result
    return result


def test_simplified_nav_labels():
    html = INDEX.read_text(encoding="utf-8")
    for label in (
        "Repository Map",
        "Build Plan",
        "Investigate Bug",
        "Impact",
        "Export",
    ):
        assert label in html
    for removed in ("Command Center", "Bug Hunt", "data-view=\"intel\"", "data-view=\"bug\""):
        assert removed not in html


def test_nav_aliases_in_app_js():
    js = APP_JS.read_text(encoding="utf-8")
    assert "NAV_ALIASES" in js
    assert 'intel: "center"' in js
    assert 'bug: "investigate"' in js
    assert "ATLAS_SHOW_GRAPH_DEBUG = false" in js


def test_module_browse_panel_present():
    html = INDEX.read_text(encoding="utf-8")
    assert "moduleBrowsePanel" in html
    assert "filterModuleBrowseList" in APP_JS.read_text(encoding="utf-8")


def test_product_version_phase122():
    assert "phase122" in api.PRODUCT_VERSION


def test_investigation_grounded_paths_only(planner_scan):
    res = api.investigate_symptom("dashboard pnl is wrong")
    assert res["ok"]
    graph_paths = {
        n["path"]
        for n in (api._STATE.get("graph") or {}).get("nodes", [])
        if n.get("type") == "module" and n.get("path")
    }
    for path in res["plan"].get("likely_modules") or []:
        assert path in graph_paths


def test_build_plan_grounded_paths_only(planner_scan):
    res = api.plan_change("fix dashboard pnl display")
    assert res["ok"]
    graph_paths = {
        n["path"]
        for n in (api._STATE.get("graph") or {}).get("nodes", [])
        if n.get("type") == "module" and n.get("path")
    }
    for path in res["plan"].get("likely_affected_modules") or []:
        assert path in graph_paths


def test_graph_health_unresolved_ratio_note(planner_scan):
    summary = api.current_summary()
    gh = summary.get("graph_health") or {}
    assert gh.get("unresolved_ratio_note")


def test_visible_nav_route_views_exist():
    html = INDEX.read_text(encoding="utf-8")
    for view in ("home", "scan", "center", "build", "investigate", "impact", "export"):
        assert f'id="view-{view}"' in html


def test_planning_routes_still_registered():
    routes = set(server.ROUTES)
    assert ("POST", "/api/planning/change") in routes
    assert ("POST", "/api/planning/investigate") in routes


def test_investigation_formatter_sections(planner_scan):
    res = api.investigate_symptom("position close sometimes fails")
    assert res["ok"]
    text = res.get("formatted") or ""
    for section in ("Symptom:", "Confidence:", "Limitations:"):
        assert section in text
