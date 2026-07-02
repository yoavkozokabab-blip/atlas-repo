"""Phase 193 — Admin Console + UI polish tests.

Static UI / navigation / role-gating / privacy checks on the shipped frontend,
plus backend admin-flow checks through the accounts service.
"""
from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
ADMIN_JS = (STATIC / "atlas_admin.js").read_text(encoding="utf-8")
ACCOUNTS_JS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")


# ── Navigation + Admin Console presence ──────────────────────────────────────
def test_admin_console_view_and_tabs_present():
    assert 'id="view-admin"' in INDEX
    for tab in ("overview", "pending", "users", "access", "feedback", "audit"):
        assert f'data-tab="{tab}"' in INDEX, tab
    assert 'id="admin-users-rows"' in INDEX
    assert 'id="admin-confirm"' in INDEX  # confirmation modal for dangerous actions


def test_user_menu_replaces_loose_account_link():
    assert 'id="userMenu"' in INDEX
    assert 'id="userMenuAdmin"' in INDEX
    assert 'id="acc-admin-entry"' in INDEX
    # The redundant standalone Account button is gone from the main nav.
    assert 'data-view="accounts"' not in INDEX
    # Quickstart + Help menu remain (Phase 155 contract).
    assert 'href="quickstart.html"' in INDEX and "help-menu" in INDEX


def test_admin_link_is_role_gated():
    # Account chip / menu only reveals admin entries for admin|superadmin.
    assert "role === 'admin' || role === 'superadmin'" in ACCOUNTS_JS
    assert "userMenuAdmin" in ACCOUNTS_JS and "acc-admin-entry" in ACCOUNTS_JS
    assert "isAdmin: _isAdmin" in ACCOUNTS_JS


def test_admin_route_blocked_for_non_admin():
    # go('admin') refuses unless atlasAccounts.isAdmin() is true.
    assert 'view === "admin"' in APP_JS
    assert "atlasAccounts.isAdmin" in APP_JS


# ── Privacy: no secrets surfaced in the admin UI/proxies ─────────────────────
def test_admin_js_has_no_secret_fields():
    forbidden = re.compile(r"password_hash|refresh_hash|refresh_token|access_token|jwt_secret", re.IGNORECASE)
    assert not forbidden.search(ADMIN_JS)


def test_admin_proxy_routes_registered_without_secrets():
    routes_py = (Path(__file__).resolve().parents[1] / "accounts_routes.py").read_text(encoding="utf-8")
    for route in (
        "/api/accounts/admin/dashboard",
        "/api/accounts/admin/audit-log",
        "/api/accounts/admin/users/grant-beta",
        "/api/accounts/admin/users/revoke-beta",
        "/api/accounts/admin/users/force-logout",
        "/api/accounts/admin/users/update",
    ):
        assert route in routes_py, route
    forbidden = re.compile(r"password_hash|refresh_hash|refresh_token", re.IGNORECASE)
    assert not forbidden.search(routes_py)


def test_desktop_registers_admin_proxy_routes():
    from jarvis_desktop.accounts_routes import ACCOUNTS_ROUTES
    keys = set(ACCOUNTS_ROUTES.keys())
    assert ("GET", "/api/accounts/admin/dashboard") in keys
    assert ("POST", "/api/accounts/admin/users/grant-beta") in keys
    assert ("POST", "/api/accounts/admin/users/update") in keys
    assert ("POST", "/api/accounts/admin/users/force-logout") in keys
    assert ("GET", "/api/accounts/admin/audit-log") in keys


# ── Backend admin flows (accounts service) ───────────────────────────────────
os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_193.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-193")
_LIB = os.path.join(Path(__file__).resolve().parents[2], "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from fastapi.testclient import TestClient  # noqa: E402
from accounts_service.database import Base, SessionLocal, engine  # noqa: E402
from accounts_service.main import app  # noqa: E402
from accounts_service.models import User  # noqa: E402
from accounts_service.rate_limit import reset_rate_limit_store  # noqa: E402

PROFILE = {
    "currently_developer": True, "project_use": "work", "company_size": "2_10",
    "developer_experience": "3_5", "primary_role": "full_stack", "coding_tools": ["claude"],
    "repo_size": "small", "atlas_help": ["planning_changes"],
}


@pytest.fixture(autouse=True)
def _reset():
    reset_rate_limit_store()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _reg(client, email=None, profile=None):
    email = email or f"u_{secrets.token_hex(5)}@example.com"
    device = secrets.token_hex(16)
    r = client.post("/auth/register", json={
        "email": email, "password": "SecurePass1!", "confirm_password": "SecurePass1!",
        "device_id": device, "app_version": "0.1.0-beta", "platform": "test",
        "beta_profile": profile if profile is not None else PROFILE,
    })
    assert r.status_code == 201, r.text
    d = r.json(); d["_email"] = email; d["_device"] = device
    return d


def _login(client, reg):
    lg = client.post("/auth/login", json={
        "email": reg["_email"], "password": "SecurePass1!",
        "device_id": reg["_device"], "app_version": "0.1.0-beta", "platform": "test",
    })
    assert lg.status_code == 200, lg.text
    return {"Authorization": f"Bearer {lg.json()['access_token']}"}


def _superadmin(client):
    a = _reg(client, email=f"admin_{secrets.token_hex(4)}@example.com")
    with SessionLocal() as db:
        db.query(User).filter(User.user_id == a["user"]["user_id"]).update({"role": "superadmin"})
        db.commit()
    return _login(client, a)


def test_pending_applications_show_profile_fields(client):
    h = _superadmin(client)
    applicant = _reg(client)
    r = client.get("/admin/applications/pending", headers=h)
    assert r.status_code == 200
    row = next(a for a in r.json() if a["email"] == applicant["_email"])
    bp = row["beta_profile"]
    assert bp["primary_role"] == "full_stack" and bp["developer_experience"] == "3_5"
    assert bp["company_size"] == "2_10" and bp["repo_size"] == "small"


def test_approve_applicant_updates_status(client):
    h = _superadmin(client)
    applicant = _reg(client)
    r = client.post(f"/admin/users/{applicant['user']['user_id']}/approve-application", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] in ("beta", "active")


def test_user_table_hides_secret_fields(client):
    h = _superadmin(client)
    _reg(client)
    r = client.get("/admin/users?limit=50", headers=h)
    assert r.status_code == 200
    blob = str(r.json()).lower()
    for forbidden in ("password_hash", "refresh_hash", "refresh_token", "access_token"):
        assert forbidden not in blob


def test_license_update_and_force_logout(client):
    h = _superadmin(client)
    u = _reg(client)
    uid = u["user"]["user_id"]
    r = client.patch(f"/admin/users/{uid}", json={"plan": "pro", "max_devices": 3, "status": "active"}, headers=h)
    assert r.status_code == 200
    assert r.json()["license"]["plan"] == "pro" and r.json()["license"]["max_devices"] == 3
    fl = client.post(f"/admin/users/{uid}/force-logout", headers=h)
    assert fl.status_code == 204


def test_suspend_ban_reinstate(client):
    h = _superadmin(client)
    uid = _reg(client)["user"]["user_id"]
    assert client.patch(f"/admin/users/{uid}", json={"status": "suspended"}, headers=h).status_code == 200
    assert client.patch(f"/admin/users/{uid}", json={"status": "banned"}, headers=h).status_code == 200
    assert client.patch(f"/admin/users/{uid}", json={"status": "active"}, headers=h).status_code == 200


def test_audit_log_records_admin_actions(client):
    h = _superadmin(client)
    uid = _reg(client)["user"]["user_id"]
    client.post(f"/admin/users/{uid}/grant-beta", headers=h)
    r = client.get("/admin/audit-log", headers=h)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "grant_beta" in actions
    blob = str(r.json()).lower()
    for forbidden in ("password_hash", "refresh_hash", "access_token"):
        assert forbidden not in blob


def test_non_admin_cannot_reach_admin_endpoints(client):
    user = _reg(client)
    h = _login(client, user)
    assert client.get("/admin/users", headers=h).status_code == 403
    assert client.get("/admin/dashboard", headers=h).status_code == 403
