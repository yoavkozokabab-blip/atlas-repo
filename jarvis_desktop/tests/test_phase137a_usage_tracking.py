"""Phase 137A — usage tracking and billing-ready infrastructure tests."""

from __future__ import annotations

import os

import pytest

from jarvis_desktop import api
from jarvis_desktop import server
from jarvis_desktop.usage import (
    default_store,
    estimate_repo_cost,
    get_plan,
    list_plans,
    pricing_payload,
    record_event,
    usage_admin_summary,
    usage_me_summary,
)


@pytest.fixture
def usage_store(tmp_path, monkeypatch):
    d = tmp_path / "usage"
    d.mkdir()
    monkeypatch.setenv("ATLAS_USAGE_DATA_DIR", str(d))
    store = default_store()
    store.reset()
    return store


def test_scan_usage_event_recorded(usage_store):
    res = record_event(
        "scan_completed",
        repo_path="/tmp/demo",
        repo_name="demo",
        files_count=120,
        modules_count=40,
        edges_count=90,
        symbols_count=200,
        scan_duration_seconds=12.5,
        store=usage_store,
    )
    assert res["ok"]
    ev = res["event"]
    assert ev["event_type"] == "scan_completed"
    assert ev["files_count"] == 120
    assert ev["estimated_token_equivalent"] > 0
    assert len(usage_store.all_events()) == 1


def test_usage_summary_aggregates(usage_store):
    record_event("scan_completed", repo_path="/a", repo_name="a", files_count=500, store=usage_store)
    record_event("export_created", repo_path="/a", repo_name="a", store=usage_store)
    record_event("scan_completed", repo_path="/b", repo_name="b", files_count=900, store=usage_store)
    me = usage_me_summary(usage_store)
    assert me["ok"]
    assert me["usage"]["scans_used"] == 2
    assert me["usage"]["exports_used"] == 1
    assert me["usage"]["repositories_used"] == 2
    assert len(me["largest_repos"]) >= 1


def test_plan_limits_load():
    plan = get_plan("FREE")
    limits = plan["limits"]
    assert limits["max_scans_per_month"] == 30
    assert limits["large_repo_allowed"] is False
    assert get_plan("ENTERPRISE")["limits"]["max_repositories"] == -1
    assert len(list_plans()) == 4


def test_pricing_data_loads():
    payload = pricing_payload()
    assert payload["ok"]
    assert payload["checkout_enabled"] is False
    assert payload["payment_provider"] is None
    assert len(payload["plans"]) == 4


def test_admin_summary_works(usage_store):
    record_event("scan_completed", repo_path="/slow", repo_name="slow", scan_duration_seconds=99, store=usage_store)
    admin = usage_admin_summary(usage_store, is_admin=True)
    assert admin["ok"]
    assert admin["total_scans"] >= 1
    assert admin["slowest_scans"][0]["duration_sec"] == 99


def test_admin_forbidden_for_non_admin(usage_store):
    admin = usage_admin_summary(usage_store, is_admin=False)
    assert admin["ok"] is False


def test_api_endpoints(usage_store, monkeypatch):
    monkeypatch.setattr(api.usage_tracking, "default_store", lambda: usage_store)
    api._STATE.update({"scan": {"repo_path": "/x", "repo_name": "x", "file_count": 10, "module_count": 3, "dependency_edges": 2}})
    status, me = server.dispatch("GET", "/api/usage/me")
    assert status == 200 and me["ok"]
    status, plans = server.dispatch("GET", "/api/plans")
    assert status == 200 and plans["plans"]
    status, pricing = server.dispatch("GET", "/api/pricing")
    assert status == 200 and pricing["plans"]
    status, posted = server.dispatch("POST", "/api/usage/event", {"event_type": "impact_created"})
    assert status == 200 and posted["ok"]


def test_billing_ui_flag_in_health(monkeypatch):
    monkeypatch.delenv("ATLAS_BILLING_UI_ENABLED", raising=False)
    h = api.health()
    assert h["billing_ui_enabled"] is False
    monkeypatch.setenv("ATLAS_BILLING_UI_ENABLED", "1")
    h2 = api.health()
    assert h2["billing_ui_enabled"] is True


def test_no_stripe_in_usage_module():
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "usage")
    hits = []
    for name in os.listdir(root):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(root, name), encoding="utf-8").read().lower()
        if "import stripe" in text or "stripe.checkout" in text:
            hits.append(name)
    assert not hits


def test_estimator_labels():
    est = estimate_repo_cost(1000, 200, 500, 100, 30)
    assert est["size_tier"] in ("small", "medium", "large", "huge")
    assert "token-equivalent" in est["token_equivalent_label"]
    assert est["recommended_plan"] in ("FREE", "PRO", "TEAM", "ENTERPRISE")
