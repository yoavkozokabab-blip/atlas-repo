"""Phase 115B — desktop graph build budgets and scan progress."""

from __future__ import annotations

import json
from pathlib import Path

from jarvis_desktop import api, graph_build, server


def test_graph_build_plan_massive_tier():
    plan = graph_build.graph_build_plan(massive_mode=True, code_files=100, estimated_modules=50)
    assert plan["detail"] == graph_build.DETAIL_IMPORTS
    assert plan["lazy_full"] is True
    assert plan["tier"] == "massive"


def test_graph_build_plan_small_tier():
    plan = graph_build.graph_build_plan(massive_mode=False, code_files=40, estimated_modules=20)
    assert plan["detail"] == graph_build.DETAIL_FULL
    assert plan["lazy_full"] is False


def test_scan_status_reports_progress_pct(tmp_path):
    api._STATE["scan_job"] = {"id": "x", "cancelled": False, "stage": "building_graph", "graph_progress": {"current": 5, "total": 10}}
    status = api.scan_status()
    assert status["ok"] is True
    assert status["progress_pct"] > 18
    assert "Building dependency graph" in status["stage_label"]


def test_build_full_graph_route_registered():
    handlers = server._route_handlers()
    assert ("POST", "/api/repositories/current/build-full-graph") in handlers


def test_scan_small_repo_completes(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    result = api.scan_repository(str(root))
    assert result["ok"] is True
    assert result.get("graph_detail") in (graph_build.DETAIL_FULL, graph_build.DETAIL_IMPORTS)


def test_frontend_polls_scan_status():
    text = Path(__file__).resolve().parents[1].joinpath("static", "app.js").read_text(encoding="utf-8")
    assert "pollScanProgress" in text
    assert "/api/repositories/current/scan-status" in text
