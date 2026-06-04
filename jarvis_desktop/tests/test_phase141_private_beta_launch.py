"""Phase 141 — Private beta launch preparation."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, server

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture(autouse=True)
def _demo_loaded():
    server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    yield


def test_beta_diagnostics_endpoint():
    _, diag = server.dispatch("GET", "/api/system/diagnostics")
    assert diag["ok"] is True
    assert diag["version"] == api.PRODUCT_VERSION
    assert "scan_statistics" in diag
    stats = diag["scan_statistics"]
    assert stats["module_count"] >= 1
    assert "file_count" in stats
    assert diag["repository"]["demo_mode"] is True


def test_health_reports_phase141_version():
    _, h = server.dispatch("GET", "/api/health")
    assert h["ok"] is True
    assert "phase141" in h["version"]


def test_workflow_runs_for_markdown_bundle_context():
    _, plan = server.dispatch("POST", "/api/planning/change", {"request": "Add logging"})
    assert plan["ok"] and plan.get("formatted")
    _, inv = server.dispatch("POST", "/api/planning/investigate", {"symptom": "wrong output"})
    assert inv["ok"] and inv.get("formatted")
    _, imp = server.dispatch("POST", "/api/planning/impact", {"target": "core/util.py"})
    assert imp["ok"]


def test_launch_ui_assets():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    beta = (STATIC / "atlas_beta.js").read_text(encoding="utf-8")
    fb = (STATIC / "feedback.js").read_text(encoding="utf-8")
    about = (STATIC / "about.html").read_text(encoding="utf-8")
    assert "welcomeScreen" in html
    assert "guidedWalkthroughPanel" in html
    assert "Report Issue" in html
    assert "aboutAtlasModal" in html
    assert "workflowFeedbackHtml" in beta
    assert "downloadWorkflowMarkdownBundle" in beta
    assert "beta_diagnostics" not in beta
    assert "/api/system/diagnostics" in beta
    assert "openReportIssue" in fb
    assert "What Atlas does" in about
    assert "What Atlas does not do" in about


def test_launch_report_exists():
    report = Path(__file__).resolve().parents[2] / "reports" / "phase141_private_beta_launch.md"
    assert report.is_file()
    assert "readiness" in report.read_text(encoding="utf-8").lower()
