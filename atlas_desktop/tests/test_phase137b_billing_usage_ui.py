"""Phase 137B — billing / usage UI real-data polish tests."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from atlas_desktop import api
from atlas_desktop import server
from atlas_desktop.usage import default_store, record_event, usage_admin_summary, usage_me_summary

STATIC = Path(__file__).resolve().parents[1] / "static"
BILLING_JS = STATIC / "billing.js"


@pytest.fixture
def usage_store(tmp_path, monkeypatch):
    d = tmp_path / "usage"
    d.mkdir()
    monkeypatch.setenv("ATLAS_USAGE_DATA_DIR", str(d))
    store = default_store()
    store.reset()
    return store


def test_usage_me_returns_valid_json(usage_store, monkeypatch):
    monkeypatch.setattr(api.usage_tracking, "default_store", lambda: usage_store)
    record_event("scan_completed", repo_path="/demo", repo_name="demo", files_count=42, store=usage_store)
    status, payload = server.dispatch("GET", "/api/usage/me")
    assert status == 200
    assert payload["ok"] is True
    assert "usage" in payload
    assert "plan" in payload
    assert payload["payments_active"] is False
    assert payload["usage"]["scans_used"] == 1
    assert "estimated_atlas_compute_units" in payload


def test_usage_admin_exists_and_handles_admin_modes(usage_store, monkeypatch):
    monkeypatch.setattr(api.usage_tracking, "default_store", lambda: usage_store)
    record_event("scan_completed", repo_path="/a", repo_name="a", store=usage_store)

    status, disabled = server.dispatch("GET", "/api/usage/admin")
    assert status == 200
    assert disabled["ok"] is False
    assert disabled.get("code") == "admin_disabled"
    assert "ATLAS_ADMIN=1" in disabled["error"]

    monkeypatch.setenv("ATLAS_ADMIN", "1")
    status, enabled = server.dispatch("GET", "/api/usage/admin")
    assert status == 200
    assert enabled["ok"] is True
    assert enabled["total_scans"] >= 1
    assert "total_repositories" in enabled
    assert "total_build_plans" in enabled
    assert "recent_events" in enabled
    assert "estimated_atlas_compute_units" in enabled

    status, alias = server.dispatch("GET", "/api/usage/admin_summary")
    assert status == 200
    assert alias["ok"] is True


def test_plans_returns_four_plans():
    status, payload = server.dispatch("GET", "/api/plans")
    assert status == 200
    assert payload["ok"] is True
    ids = {p["id"] for p in payload["plans"]}
    assert ids == {"FREE", "PRO", "TEAM", "ENTERPRISE"}


def test_pricing_returns_plan_data():
    status, payload = server.dispatch("GET", "/api/pricing")
    assert status == 200
    assert payload["ok"] is True
    assert payload["checkout_enabled"] is False
    assert payload["payment_provider"] is None
    assert len(payload["plans"]) == 4


def test_pricing_html_has_plan_render_targets():
    html = (STATIC / "pricing.html").read_text(encoding="utf-8")
    assert 'data-billing-page="pricing"' in html
    assert 'id="planGrid"' in html
    for plan in ("FREE", "PRO", "TEAM", "ENTERPRISE"):
        assert plan in html


def test_usage_html_has_dashboard_render_targets():
    html = (STATIC / "usage.html").read_text(encoding="utf-8")
    assert 'data-billing-page="usage"' in html
    for target in ("usageCards", "planCard", "limits", "largestRepos", "recentEvents", "emptyState"):
        assert f'id="{target}"' in html


def test_billing_admin_html_has_admin_render_targets():
    html = (STATIC / "billing_admin.html").read_text(encoding="utf-8")
    assert 'data-billing-page="admin"' in html
    assert 'id="adminBody"' in html
    assert "admin-dashboard" in html


def test_billing_js_uses_known_endpoints_only():
    text = BILLING_JS.read_text(encoding="utf-8")
    paths = re.findall(r'"/api/[^"]+"', text)
    allowed = {
        "/api/health",
        "/api/usage/me",
        "/api/billing/usage",
        "/api/usage/admin",
        "/api/usage/admin_summary",
        "/api/billing/admin",
        "/api/plans",
        "/api/billing/plans",
        "/api/pricing",
    }
    for p in paths:
        assert p.strip('"') in allowed, f"unexpected endpoint reference: {p}"


def test_no_stripe_or_checkout_references_in_billing_ui():
    files = [STATIC / "billing.js", STATIC / "pricing.html", STATIC / "usage.html", STATIC / "billing_admin.html"]
    banned = ("stripe.com", "checkout.stripe", "import stripe", "stripe.checkout")
    for path in files:
        lower = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in lower, f"{path.name} contains {token}"


def test_billing_ui_flag_hides_nav_links_in_index(monkeypatch):
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="billingNav"' in index
    monkeypatch.delenv("ATLAS_BILLING_UI_ENABLED", raising=False)
    assert api.health()["billing_ui_enabled"] is False


def test_usage_me_empty_state_message(usage_store):
    me = usage_me_summary(usage_store)
    assert me["ok"] is True
    assert me["has_usage_data"] is False
    assert "No usage recorded yet" in me["empty_state_message"]


def test_admin_summary_legacy_fields(usage_store):
    record_event("build_plan_created", repo_path="/x", repo_name="x", store=usage_store)
    admin = usage_admin_summary(usage_store, is_admin=True)
    assert admin["largest_repos"]
    assert admin["largest_repositories"] == admin["largest_repos"]
