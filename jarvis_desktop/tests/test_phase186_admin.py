"""Phase 186 — Atlas Admin Console tests.

Tests cover:
  - /admin/dashboard returns metric counts
  - /admin/users returns paginated list
  - /admin/users/{id} GET returns user details
  - PATCH /admin/users/{id} updates status/beta_flag/plan
  - POST /admin/users/{id}/grant-beta promotes user
  - POST /admin/users/{id}/revoke-beta demotes user
  - POST /admin/users/{id}/force-logout revokes all sessions
  - DELETE /admin/users/{id}/devices/{device_id} revokes device
  - GET /admin/audit-log returns log entries after each action
  - Banning requires superadmin role
  - Role changes require superadmin role
  - Non-admin users get 403 on all admin routes
  - GET /admin/feedback returns feedback list
"""
from __future__ import annotations

import os
import secrets
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_admin_186.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "admin-test-secret-186")

from fastapi.testclient import TestClient
from accounts_service.main import app
from accounts_service.database import Base, engine, SessionLocal
from accounts_service import models

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    for f in ["test_admin_186.db"]:
        if os.path.exists(f):
            try:
                os.unlink(f)
            except OSError:
                pass


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _rand_email():
    return f"admin_{secrets.token_hex(5)}@test.dev"


def _device():
    return secrets.token_hex(16)


def _register(client, email=None, password="TestPass1!"):
    email = email or _rand_email()
    device = _device()
    r = client.post("/auth/register", json={
        "email": email, "password": password,
        "device_id": device, "app_version": "0.1.0", "platform": "test"
    })
    return r.json(), email, device


def _make_admin(email: str, role: str = "admin"):
    with SessionLocal() as db:
        u = db.query(models.User).filter(models.User.email == email).first()
        if u:
            u.role = role
            db.commit()


def _admin_token(client) -> str:
    """Create an admin user and return its access token."""
    reg, email, _ = _register(client, email=f"admin_root_{secrets.token_hex(4)}@test.dev")
    _make_admin(email, role="superadmin")
    login = client.post("/auth/login", json={
        "email": email, "password": "TestPass1!", "device_id": _device(),
        "app_version": "0.1.0", "platform": "test"
    })
    return login.json()["access_token"]


@pytest.fixture(scope="module")
def admin_hdr(client):
    token = _admin_token(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def regular_hdr(client):
    reg, _, _ = _register(client)
    return {"Authorization": f"Bearer {reg['access_token']}"}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDashboard:
    def test_dashboard_returns_metrics(self, client, admin_hdr):
        res = client.get("/admin/dashboard", headers=admin_hdr)
        assert res.status_code == 200
        d = res.json()
        assert "total_users" in d
        assert "active_users" in d
        assert "beta_users" in d
        assert d["total_users"] >= 1

    def test_dashboard_requires_admin(self, client, regular_hdr):
        res = client.get("/admin/dashboard", headers=regular_hdr)
        assert res.status_code == 403

    def test_dashboard_unauthenticated(self, client):
        res = client.get("/admin/dashboard")
        assert res.status_code == 401


class TestUserList:
    def test_list_users_returns_array(self, client, admin_hdr):
        res = client.get("/admin/users", headers=admin_hdr)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_users_search(self, client, admin_hdr):
        # Create a uniquely named user then search for them
        unique_email = f"unique_{secrets.token_hex(8)}@findme.test"
        _register(client, email=unique_email)
        res = client.get(f"/admin/users?q=unique_{unique_email.split('_')[1][:8]}", headers=admin_hdr)
        assert res.status_code == 200
        results = res.json()
        assert any(u["email"] == unique_email for u in results)

    def test_get_user_by_id(self, client, admin_hdr):
        reg, email, _ = _register(client)
        user_id = reg["user"]["user_id"]
        res = client.get(f"/admin/users/{user_id}", headers=admin_hdr)
        assert res.status_code == 200
        assert res.json()["email"] == email

    def test_get_user_nonexistent(self, client, admin_hdr):
        res = client.get("/admin/users/nonexistent-id-xyz", headers=admin_hdr)
        assert res.status_code == 404


class TestUserActions:
    def test_grant_beta(self, client, admin_hdr):
        reg, _, _ = _register(client)
        uid = reg["user"]["user_id"]
        res = client.post(f"/admin/users/{uid}/grant-beta", headers=admin_hdr)
        assert res.status_code == 200
        u = res.json()
        assert u["beta_flag"] is True
        assert u["status"] == "beta"

    def test_revoke_beta(self, client, admin_hdr):
        reg, _, _ = _register(client)
        uid = reg["user"]["user_id"]
        client.post(f"/admin/users/{uid}/grant-beta", headers=admin_hdr)
        res = client.post(f"/admin/users/{uid}/revoke-beta", headers=admin_hdr)
        assert res.status_code == 200
        u = res.json()
        assert u["beta_flag"] is False
        assert u["status"] in ("active", "free")

    def test_patch_user_status(self, client, admin_hdr):
        reg, _, _ = _register(client)
        uid = reg["user"]["user_id"]
        res = client.patch(f"/admin/users/{uid}", json={"status": "suspended"}, headers=admin_hdr)
        assert res.status_code == 200
        assert res.json()["status"] == "suspended"

    def test_patch_ban_requires_superadmin(self, client):
        # Create an admin (not superadmin)
        reg, email, _ = _register(client, email=f"plain_admin_{secrets.token_hex(4)}@test.dev")
        _make_admin(email, role="admin")  # regular admin, not superadmin
        login = client.post("/auth/login", json={
            "email": email, "password": "TestPass1!", "device_id": _device(),
            "app_version": "0.1.0", "platform": "test"
        })
        admin_token = login.json()["access_token"]
        hdr = {"Authorization": f"Bearer {admin_token}"}

        # Create a target user
        reg2, _, _ = _register(client)
        uid = reg2["user"]["user_id"]

        res = client.patch(f"/admin/users/{uid}", json={"status": "banned"}, headers=hdr)
        assert res.status_code == 403

    def test_patch_role_requires_superadmin(self, client):
        reg, email, _ = _register(client, email=f"plain_a2_{secrets.token_hex(4)}@test.dev")
        _make_admin(email, role="admin")
        login = client.post("/auth/login", json={
            "email": email, "password": "TestPass1!", "device_id": _device(),
            "app_version": "0.1.0", "platform": "test"
        })
        hdr = {"Authorization": f"Bearer {login.json()['access_token']}"}

        reg2, _, _ = _register(client)
        uid = reg2["user"]["user_id"]
        res = client.patch(f"/admin/users/{uid}", json={"role": "admin"}, headers=hdr)
        assert res.status_code == 403

    def test_force_logout_revokes_sessions(self, client, admin_hdr):
        reg, email, device = _register(client)
        uid = reg["user"]["user_id"]
        refresh = reg["refresh_token"]

        client.post(f"/admin/users/{uid}/force-logout", headers=admin_hdr)

        # The refresh token must be rejected
        res = client.post("/auth/refresh", json={"refresh_token": refresh, "device_id": device})
        assert res.status_code == 401


class TestDeviceRevocation:
    def test_admin_revoke_device(self, client, admin_hdr):
        reg, email, device = _register(client)
        uid = reg["user"]["user_id"]
        res = client.delete(f"/admin/users/{uid}/devices/{device}", headers=admin_hdr)
        assert res.status_code == 204

    def test_revoke_nonexistent_device(self, client, admin_hdr):
        reg, _, _ = _register(client)
        uid = reg["user"]["user_id"]
        res = client.delete(f"/admin/users/{uid}/devices/nonexistent-device", headers=admin_hdr)
        assert res.status_code == 404


class TestAuditLog:
    def test_audit_log_populated_after_action(self, client, admin_hdr):
        reg, _, _ = _register(client)
        uid = reg["user"]["user_id"]
        client.post(f"/admin/users/{uid}/grant-beta", headers=admin_hdr)

        res = client.get("/admin/audit-log", headers=admin_hdr)
        assert res.status_code == 200
        entries = res.json()
        assert len(entries) >= 1
        actions = [e["action"] for e in entries]
        assert "grant_beta" in actions

    def test_audit_log_requires_admin(self, client, regular_hdr):
        res = client.get("/admin/audit-log", headers=regular_hdr)
        assert res.status_code == 403


class TestFeedback:
    def test_feedback_list_accessible_to_admin(self, client, admin_hdr):
        res = client.get("/admin/feedback", headers=admin_hdr)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_feedback_list_blocked_for_user(self, client, regular_hdr):
        res = client.get("/admin/feedback", headers=regular_hdr)
        assert res.status_code == 403
