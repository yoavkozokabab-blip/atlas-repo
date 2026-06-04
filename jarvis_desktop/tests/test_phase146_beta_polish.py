"""Phase 146 — beta polish (copy, onboarding, first Build Plan funnel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_desktop import api, server

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _demo_loaded():
    server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    yield


def test_version_phase146():
    assert "phase146" in api.PRODUCT_VERSION


def test_first_build_plan_works_on_demo():
    _, plan = server.dispatch(
        "POST",
        "/api/planning/change",
        {"request": "Add structured logging to API handlers"},
    )
    assert plan["ok"] is True
    assert plan.get("formatted")
    assert (plan.get("plan") or {}).get("implementation_order")


def test_polish_ui_markers():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    polish = (STATIC / "atlas_polish.js").read_text(encoding="utf-8")
    support = (STATIC / "support.html").read_text(encoding="utf-8")
    assert "Planning only" in html
    assert "goToFirstBuildPlan" in html
    assert "promptFirstBuildPlanAfterScan" in polish
    assert "friendlyValidateMessage" in polish
    assert "markFirstBuildPlanDone" in app
    assert "pip install failed" in support and "requirements.txt" in support
    assert "Load Sample Repository" in html
    assert "Product Tour (auto)" not in html


def test_quickstart_doc_exists():
    doc = ROOT / "docs" / "ATLAS_QUICKSTART.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "pip install" in text.lower()
    assert "Load Sample" in text


def test_phase146_report_exists():
    report = ROOT / "reports" / "phase146_beta_polish.md"
    assert report.is_file()
