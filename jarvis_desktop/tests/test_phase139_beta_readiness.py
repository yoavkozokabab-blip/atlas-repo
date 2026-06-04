"""Phase 139 — Private beta readiness (product UX, health, onboarding)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, server

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture(autouse=True)
def _demo_loaded():
    server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    yield


def test_system_health_endpoint_after_scan():
    _, health = server.dispatch("GET", "/api/repositories/current/system-health")
    assert health["ok"] is True
    for key in (
        "indexed_files",
        "modules",
        "edges",
        "unresolved_imports",
        "scan_duration_seconds",
        "graph_quality",
        "evidence_coverage",
        "scan_performance",
        "workflow_performance",
    ):
        assert key in health, key
    ev = health["evidence_coverage"]
    assert "symbol_count" in ev
    assert "files_with_symbols" in ev


def test_summary_includes_evidence_coverage():
    _, summary = server.dispatch("GET", "/api/repositories/current/summary")
    assert summary["ok"] is True
    assert "evidence_coverage" in summary
    assert "scan_duration_seconds" in summary


def test_workflow_performance_recorded():
    _, plan = server.dispatch(
        "POST",
        "/api/planning/change",
        {"request": "Add structured logging to API handlers"},
    )
    assert plan["ok"] is True
    _, inv = server.dispatch(
        "POST",
        "/api/planning/investigate",
        {"symptom": "API requests fail intermittently"},
    )
    assert inv["ok"] is True
    _, impact = server.dispatch("POST", "/api/planning/impact", {"target": "core/hub.py"})
    assert impact["ok"] is True
    _, health = server.dispatch("GET", "/api/repositories/current/system-health")
    wf = health["workflow_performance"]
    assert wf.get("build_plan", {}).get("duration_ms", 0) >= 0
    assert wf.get("investigation", {}).get("duration_ms", 0) >= 0
    assert wf.get("impact", {}).get("duration_ms", 0) >= 0


def test_validate_error_codes_for_recovery():
    empty = api.validate_repository_path("")
    assert empty["ok"] is False and empty["code"] == "empty_path"
    missing = api.validate_repository_path("/nonexistent/atlas/phase139")
    assert missing["ok"] is False and missing["code"] == "not_found"


def test_demo_load_lists_packs():
    _, packs = server.dispatch("GET", "/api/demo/packs")
    assert packs["ok"] is True
    assert len(packs.get("packs") or []) >= 1


def test_onboarding_and_health_ui_wired():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "onboard-steps-grid" in html
    assert "Load Sample Repository" in html
    assert "System Health" in app_js
    assert "beta_system_health" not in app_js
    assert "/api/repositories/current/system-health" in app_js
    assert "renderWorkflowGate" in app_js
    assert "showScanFailed" in app_js
    assert ".empty-panel" in css
    assert ".recent-card" in css


def test_beta_readiness_report_exists():
    report = Path(__file__).resolve().parents[2] / "reports" / "phase139_beta_readiness.md"
    assert report.is_file()
    text = report.read_text(encoding="utf-8")
    assert "readiness score" in text.lower()
    assert "remaining blockers" in text.lower()
