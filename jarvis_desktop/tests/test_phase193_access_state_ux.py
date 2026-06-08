"""Phase 193 — Access State UX redesign.

A successful login must never strand the user on a blocking "Access inactive"
wall. Every signed-in account resolves to a useful in-app dashboard:

    active / beta      -> product home (with a dashboard header)
    pending            -> "Application received" dashboard
    inactive / expired -> "Account not active" dashboard
    rejected           -> "Application not approved" dashboard

This module covers the static frontend contract plus the accounts-service
behaviour that makes those states reachable (non-punitive statuses now receive a
token at login instead of a 403).
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
ACCOUNTS_JS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")
ACCOUNTS_CLIENT = (Path(__file__).resolve().parents[1] / "accounts_client.py").read_text(encoding="utf-8")


# ── Static frontend contract ──────────────────────────────────────────────────
def test_in_app_status_view_exists_with_branding_kept():
    # A dedicated in-app status view (rendered inside the app shell, so the Atlas
    # topbar/nav stay visible) — not the pre-login auth wall.
    assert 'id="view-status"' in INDEX
    assert 'id="statusDashTitle"' in INDEX
    assert 'id="statusDashMessage"' in INDEX
    assert 'id="statusDashSteps"' in INDEX
    # The status view lives in #app (after the topbar), not inside #auth-layout.
    app_pos = INDEX.find('<main id="app">')
    auth_pos = INDEX.find('id="auth-layout"')
    assert auth_pos < app_pos < INDEX.find('id="view-status"')


def test_status_dashboards_have_required_actions():
    # Refresh status, contact support, sign out, and a (future) reapply option.
    assert 'id="statusRefreshBtn"' in INDEX
    assert "Refresh account status" in INDEX
    assert "atlasAccounts.refreshStatus()" in INDEX
    assert 'id="statusReapplyBtn"' in INDEX
    assert "atlasAccounts.reapply()" in INDEX
    assert 'href="support.html"' in INDEX
    assert "atlasAccounts.logout()" in INDEX


def test_status_dashboard_titles_match_spec():
    for title in ("Application received", "Account not active", "Application not approved"):
        assert title in ACCOUNTS_JS, title


def test_home_dashboard_present_with_quick_actions():
    assert 'id="homeDashboard"' in INDEX
    assert 'id="homeWelcome"' in INDEX
    assert 'id="homeStatusPill"' in INDEX
    assert 'id="homeRepoStatus"' in INDEX
    assert 'id="homeRecentAnalyses"' in INDEX
    quick = INDEX[INDEX.find('class="quick-action-cards"'):]
    for action in ("Scan Repository", "Change Plan", "Debug Issue", "What Breaks"):
        assert action in quick, action


def test_client_routes_signed_in_inactive_users_into_app():
    # State exposes a signed_in flag distinct from full authentication.
    assert '"signed_in"' in ACCOUNTS_CLIENT
    assert "signed_in" in ACCOUNTS_JS
    # Status taxonomy + dashboards exist and are wired.
    for fn in ("_accountStatus", "_renderStatusDashboard", "_renderHomeDashboard", "function refreshStatus"):
        assert fn in ACCOUNTS_JS, fn
    # Signed-in-but-inactive users are routed to the in-app status view.
    assert "go('status')" in ACCOUNTS_JS
    # requireAccess no longer dead-ends signed-in users on the pre-login wall.
    assert "_state.signed_in" in ACCOUNTS_JS


def test_no_forced_home_redirect_for_inactive_login():
    # doLogin must route via layout sync, not force every login to home.
    login_block = ACCOUNTS_JS[ACCOUNTS_JS.find("function doLogin"):ACCOUNTS_JS.find("function doLogin") + 1200]
    assert "_enterApp({ goHome: true })" not in login_block


def test_status_dashboard_styles_present():
    assert ".status-dash" in CSS
    assert ".home-dashboard" in CSS
    assert ".status-pill" in CSS


# ── Accounts-service behaviour ──────────────────────────────────────────────────
os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_193ux.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-193ux")
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


def _reg(client, email=None):
    email = email or f"u_{secrets.token_hex(5)}@example.com"
    device = secrets.token_hex(16)
    r = client.post("/auth/register", json={
        "email": email, "password": "SecurePass1!", "confirm_password": "SecurePass1!",
        "device_id": device, "app_version": "0.1.0-beta", "platform": "test",
        "beta_profile": PROFILE,
    })
    assert r.status_code == 201, r.text
    d = r.json(); d["_email"] = email; d["_device"] = device
    return d


def _login(client, reg):
    return client.post("/auth/login", json={
        "email": reg["_email"], "password": "SecurePass1!",
        "device_id": reg["_device"], "app_version": "0.1.0-beta", "platform": "test",
    })


def _set_status(user_id, status):
    with SessionLocal() as db:
        db.query(User).filter(User.user_id == user_id).update({"status": status})
        db.commit()


def _hdr(login_resp):
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


def test_pending_user_logs_in_and_license_is_inactive(client):
    reg = _reg(client)  # registration defaults to pending
    lg = _login(client, reg)
    assert lg.status_code == 200, lg.text  # successful login, token issued
    lic = client.get("/user/license", headers=_hdr(lg))
    assert lic.status_code == 200
    assert lic.json()["valid"] is False
    assert lic.json()["status"] == "pending"


def test_inactive_user_logs_in_to_dashboard_not_403(client):
    reg = _reg(client)
    _set_status(reg["user"]["user_id"], "inactive")
    lg = _login(client, reg)
    assert lg.status_code == 200, lg.text
    lic = client.get("/user/license", headers=_hdr(lg))
    assert lic.json()["valid"] is False
    assert lic.json()["status"] == "inactive"


def test_rejected_user_logs_in_to_dashboard_not_403(client):
    reg = _reg(client)
    _set_status(reg["user"]["user_id"], "rejected")
    lg = _login(client, reg)
    assert lg.status_code == 200, lg.text
    lic = client.get("/user/license", headers=_hdr(lg))
    assert lic.json()["valid"] is False
    assert lic.json()["status"] == "rejected"


def test_suspended_and_banned_remain_hard_login_blocks(client):
    for status in ("suspended", "banned"):
        reg = _reg(client)
        _set_status(reg["user"]["user_id"], status)
        lg = _login(client, reg)
        assert lg.status_code == 403, f"{status} should be blocked at login"


def test_active_user_has_valid_license(client):
    reg = _reg(client)
    _set_status(reg["user"]["user_id"], "active")
    lg = _login(client, reg)
    assert lg.status_code == 200
    lic = client.get("/user/license", headers=_hdr(lg))
    assert lic.json()["valid"] is True
