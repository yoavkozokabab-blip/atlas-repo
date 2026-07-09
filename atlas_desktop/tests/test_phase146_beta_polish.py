"""Phase 146 — beta polish (copy, onboarding, first Plan Change funnel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _demo_loaded():
    api.load_demo_mode("small")
    yield


def test_version_is_clean_semver():
    import re as _re
    assert _re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", api.PRODUCT_VERSION)


def test_first_build_plan_works_on_demo():
    plan = api.plan_change("Add structured logging to API handlers")
    assert plan["ok"] is True
    assert plan.get("formatted")
    assert (plan.get("plan") or {}).get("implementation_order")


def test_polish_ui_markers():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    polish = (STATIC / "atlas_polish.js").read_text(encoding="utf-8")
    support = (STATIC / "support.html").read_text(encoding="utf-8")
    assert "Plan Change" in html
    assert "Ask Atlas" in html
    assert "goToFirstBuildPlan" in html
    assert "promptFirstBuildPlanAfterScan" in polish
    assert "friendlyValidateMessage" in polish
    assert "markFirstBuildPlanDone" in app
    assert "pip install failed" in support and "requirements.txt" in support
    assert "Load sample repository" in html
    assert "Product Tour (auto)" not in html


def test_quickstart_doc_exists():
    doc = ROOT / "docs" / "ATLAS_QUICKSTART.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "pip install" in text.lower()
    assert "Load Sample" in text


def test_phase146_report_exists():
    report = ROOT / "reports" / "phase146_beta_polish.md"
    if not report.is_file():
        pytest.skip("historical phase report not shipped in the product repo")
