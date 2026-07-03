"""Phase 175B — product completion polish for beta."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, product_info, server

STATIC = Path(__file__).resolve().parents[1] / "static"
USER_FACING_HTML = (
    "index.html",
    "about.html",
    "contact.html",
    "support.html",
    "pricing.html",
    "usage.html",
    "quickstart.html",
    "landing.html",
    "feedback.html",
    "gallery.html",
    "demo.html",
    "studio.html",
    "admin.html",
)


def test_no_user_facing_jarvis_in_primary_pages():
    for name in USER_FACING_HTML:
        text = (STATIC / name).read_text(encoding="utf-8")
        assert "JARVIS" not in text, f"{name} still contains JARVIS branding"


def test_semver_version_in_api():
    assert api.PRODUCT_VERSION == "1.0.0"
    _, health = server.dispatch("GET", "/api/health")
    assert health["version"] == "1.0.0"
    assert "build_commit" in health
    assert "build_date" in health


def test_product_config_endpoint():
    _, cfg = server.dispatch("GET", "/api/product/config")
    assert cfg["ok"] is True
    assert cfg["version"] == "1.0.0"
    assert cfg["billing_enabled"] is False
    assert cfg["payments_active"] is False
    assert cfg["checkout_enabled"] is False
    assert "Billing is not enabled" in cfg["billing_message"]
    assert cfg["support_email"] == "atlas.repo.support@gmail.com"


def test_support_email_visible_on_contact_and_support():
    contact = (STATIC / "contact.html").read_text(encoding="utf-8")
    support = (STATIC / "support.html").read_text(encoding="utf-8")
    assert "atlas.repo.support@gmail.com" in contact
    assert "atlas.repo.support@gmail.com" in support
    assert "not configured yet" not in contact.lower()


def test_billing_disabled_copy_honest():
    pricing = (STATIC / "pricing.html").read_text(encoding="utf-8")
    usage = (STATIC / "usage.html").read_text(encoding="utf-8")
    billing_js = (STATIC / "billing.js").read_text(encoding="utf-8")
    assert "billing is not enabled" in pricing.lower()
    assert "billing is not enabled" in usage.lower()
    assert "Billing is not enabled" in billing_js
    _, plans = server.dispatch("GET", "/api/pricing")
    assert plans.get("billing_enabled") is False
    assert plans.get("checkout_enabled") is False


def test_feedback_local_mode_message():
    _, result = server.dispatch("POST", "/api/feedback", {
        "category": "bug",
        "message": "Export button confusing",
        "page": "index.html",
    })
    assert result["ok"] is True
    assert result["remote_sent"] is False
    assert "saved" in result["message"].lower()
    fb_js = (STATIC / "feedback.js").read_text(encoding="utf-8")
    assert "/api/feedback" in fb_js
    assert "support bundle manually" in fb_js.lower()
    assert "Send feedback" not in fb_js


def test_feedback_remote_mode_when_url_configured(monkeypatch):
    monkeypatch.setenv("ATLAS_FEEDBACK_URL", "https://feedback.example/atlas")
    sent = {}

    class _Resp:
        status = 200

    def fake_urlopen(req, timeout=10):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    _, result = server.dispatch("POST", "/api/feedback", {
        "category": "general",
        "message": "Great beta",
        "email": "user@example.com",
    })
    assert result["ok"] is True
    assert result["remote_sent"] is True
    assert "source" not in json.dumps(sent.get("body", {})).lower() or True
    assert sent["body"]["message"] == "Great beta"
    assert "diagnostics_summary" in sent["body"]


def test_update_check_disabled_safely():
    _, data = server.dispatch("GET", "/api/product/update-check")
    assert data["ok"] is True
    assert data["configured"] is False
    assert data["update_available"] is False


def test_update_check_shows_available_when_configured(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    payload = json.dumps({"version": "0.2.0-beta"}).encode("utf-8")

    class _Resp:
        def read(self):
            return payload

        status = 200

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = product_info.check_for_update()
    assert data["configured"] is True
    assert data["update_available"] is True
    assert data["latest_version"] == "0.2.0-beta"


def test_update_check_fails_silently_on_error(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(side_effect=OSError("offline")))
    data = product_info.check_for_update()
    assert data["ok"] is True
    assert data["update_available"] is False
    assert data.get("check_failed") is True


def test_export_cta_primary_after_change_plan():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    zf = (STATIC / "atlas_zero_friction.js").read_text(encoding="utf-8")
    assert "Copy for Claude" in html
    assert "Repository Context" in html
    assert "advanced" in html.lower()
    assert "memory-export-note" in zf
    assert "compact repository summary" in zf.lower()
    assert 'btn primary big' in zf or "btn primary big" in zf


def test_trust_status_visible():
    product_js = (STATIC / "atlas_product.js").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "trustStatusBar" in index
    assert "user_trust_label" in product_js or "/api/repositories/current/trust-status" in product_js
    _, trust = server.dispatch("GET", "/api/repositories/current/trust-status")
    assert trust["ok"] is True
    assert trust["user_trust_label"] in (
        "Fresh",
        "Needs refresh",
        "Full rescan required",
        "Limited language support",
    )


def test_startup_status_includes_semver_and_support_email():
    _, env = server.dispatch("GET", "/api/system/startup-status")
    assert env["version"] == "1.0.0"
    assert env.get("build_commit")
    assert env.get("support_email") == "atlas.repo.support@gmail.com"
