"""Admin Workspace — analytics dashboard proxy route."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from jarvis_desktop import accounts_client, accounts_routes


def test_admin_analytics_route_unauthenticated(monkeypatch):
    monkeypatch.setattr(accounts_client, "get_admin_analytics_dashboard", lambda: {"_unauthenticated": True})
    out = accounts_routes.accounts_admin_analytics_dashboard({}, {})
    assert out["ok"] is False
    assert "sign-in" in out["error"].lower()


def test_admin_analytics_route_forwards_payload(monkeypatch):
    payload = {
        "ok": True,
        "funnel": [{"key": "install", "label": "Install", "count": 3, "conversionFromPrev": None}],
        "events_total": 10,
    }
    monkeypatch.setattr(accounts_client, "get_admin_analytics_dashboard", lambda: payload)
    out = accounts_routes.accounts_admin_analytics_dashboard({}, {})
    assert out == payload


def test_admin_analytics_route_service_unavailable(monkeypatch):
    monkeypatch.setattr(
        accounts_client,
        "get_admin_analytics_dashboard",
        lambda: {"ok": False, "_http_status": 503, "detail": "Cloud analytics require website auth."},
    )
    out = accounts_routes.accounts_admin_analytics_dashboard({}, {})
    assert out["ok"] is False
    assert "website auth" in out["error"].lower()
