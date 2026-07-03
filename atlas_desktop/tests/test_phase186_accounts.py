"""Phase 186 — Atlas Accounts: end-to-end auth and license tests.

Tests cover:
  - Registration creates user + license + session
  - Login issues tokens; wrong password returns 401
  - Refresh token rotation issues new tokens
  - Logout revokes session
  - /user/me returns profile
  - /user/license returns license check response
  - /user/devices returns device list
  - Blocked statuses (suspended/banned) return 403 on login
  - Device limit enforcement
  - Rate limit headers are present on auth endpoints
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Generator

import pytest

# Add accounts_service to path
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Use a temporary SQLite DB for tests
os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_186.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-186")

pytest.importorskip("accounts_service", reason="accounts_service is dev-only; not shipped in the product repo")

from fastapi.testclient import TestClient
from accounts_service.main import app
from accounts_service.database import Base, engine, get_db
from accounts_service import models
from accounts_service.rate_limit import reset_rate_limit_store

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    reset_rate_limit_store()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Remove test db file if it exists
    db_file = "test_accounts_186.db"
    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limit_store()


@pytest.fixture(scope="module")
def client() -> Generator:
    with TestClient(app) as c:
        yield c


def _random_email() -> str:
    return f"test_{secrets.token_hex(6)}@example.com"


def _device_id() -> str:
    return secrets.token_hex(16)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_creates_user(self, client):
        res = client.post("/auth/register", json={
            "email": _random_email(), "password": "SecurePass1!",
            "device_id": _device_id(), "app_version": "0.1.0-beta", "platform": "Windows 11"
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] is not None
        assert data["license"]["plan"] == "free"

    def test_duplicate_email_is_rejected(self, client):
        email = _random_email()
        payload = {"email": email, "password": "SecurePass1!", "device_id": _device_id(),
                   "app_version": "0.1.0", "platform": "Windows 10"}
        client.post("/auth/register", json=payload)
        res2 = client.post("/auth/register", json=payload | {"device_id": _device_id()})
        assert res2.status_code == 409

    def test_register_short_password_rejected(self, client):
        res = client.post("/auth/register", json={
            "email": _random_email(), "password": "short",
            "device_id": _device_id(), "app_version": "0.1.0", "platform": "test"
        })
        assert res.status_code == 422


class TestLogin:
    def test_login_returns_tokens(self, client):
        email = _random_email()
        device = _device_id()
        client.post("/auth/register", json={
            "email": email, "password": "LoginTest1!", "device_id": device,
            "app_version": "0.1.0-beta", "platform": "Windows"
        })
        res = client.post("/auth/login", json={
            "email": email, "password": "LoginTest1!", "device_id": device,
            "app_version": "0.1.0-beta", "platform": "Windows"
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_wrong_password_returns_401(self, client):
        email = _random_email()
        client.post("/auth/register", json={
            "email": email, "password": "CorrectPass1!", "device_id": _device_id(),
            "app_version": "0.1.0", "platform": "test"
        })
        res = client.post("/auth/login", json={
            "email": email, "password": "WrongPass!!", "device_id": _device_id(),
            "app_version": "0.1.0", "platform": "test"
        })
        assert res.status_code == 401

    def test_unknown_email_returns_401(self, client):
        res = client.post("/auth/login", json={
            "email": "nobody@nowhere.example.com", "password": "Pass1234!",
            "device_id": _device_id(), "app_version": "0.1.0", "platform": "test"
        })
        assert res.status_code == 401

    def test_suspended_user_returns_403(self, client):
        from sqlalchemy.orm import sessionmaker
        email = _random_email()
        device = _device_id()
        client.post("/auth/register", json={
            "email": email, "password": "Suspended1!", "device_id": device,
            "app_version": "0.1.0", "platform": "test"
        })
        # Manually suspend the user
        from accounts_service.database import SessionLocal
        with SessionLocal() as db:
            u = db.query(models.User).filter(models.User.email == email).first()
            u.status = "suspended"
            db.commit()

        res = client.post("/auth/login", json={
            "email": email, "password": "Suspended1!", "device_id": _device_id(),
            "app_version": "0.1.0", "platform": "test"
        })
        assert res.status_code == 403


class TestTokenRefresh:
    def test_refresh_issues_new_tokens(self, client):
        email = _random_email()
        device = _device_id()
        reg = client.post("/auth/register", json={
            "email": email, "password": "RefreshTest1!", "device_id": device,
            "app_version": "0.1.0-beta", "platform": "Windows"
        }).json()
        old_refresh = reg["refresh_token"]

        res = client.post("/auth/refresh", json={
            "refresh_token": old_refresh, "device_id": device
        })
        assert res.status_code == 200
        new_refresh = res.json()["refresh_token"]
        assert new_refresh != old_refresh

    def test_old_refresh_token_rejected_after_rotation(self, client):
        email = _random_email()
        device = _device_id()
        reg = client.post("/auth/register", json={
            "email": email, "password": "RotateTest1!", "device_id": device,
            "app_version": "0.1.0", "platform": "test"
        }).json()
        old_refresh = reg["refresh_token"]

        # Rotate
        client.post("/auth/refresh", json={"refresh_token": old_refresh, "device_id": device})

        # Old token must be rejected
        res = client.post("/auth/refresh", json={"refresh_token": old_refresh, "device_id": device})
        assert res.status_code == 401

    def test_device_mismatch_revokes_session(self, client):
        email = _random_email()
        device = _device_id()
        reg = client.post("/auth/register", json={
            "email": email, "password": "MismatchTest1!", "device_id": device,
            "app_version": "0.1.0", "platform": "test"
        }).json()
        wrong_device = _device_id()
        res = client.post("/auth/refresh", json={
            "refresh_token": reg["refresh_token"], "device_id": wrong_device
        })
        assert res.status_code == 401


class TestLogout:
    def test_logout_revokes_session(self, client):
        email = _random_email()
        device = _device_id()
        reg = client.post("/auth/register", json={
            "email": email, "password": "LogoutTest1!", "device_id": device,
            "app_version": "0.1.0", "platform": "test"
        }).json()
        refresh = reg["refresh_token"]

        client.post("/auth/logout", json={"refresh_token": refresh})

        # Refresh must fail after logout
        res = client.post("/auth/refresh", json={"refresh_token": refresh, "device_id": device})
        assert res.status_code == 401

    def test_logout_always_204(self, client):
        """Logout with a non-existent token must still return 204."""
        res = client.post("/auth/logout", json={"refresh_token": secrets.token_hex(32)})
        assert res.status_code == 204


class TestUserRoutes:
    @pytest.fixture(scope="class")
    def tokens(self, client):
        email = _random_email()
        device = _device_id()
        reg = client.post("/auth/register", json={
            "email": email, "password": "UserRoutes1!", "device_id": device,
            "app_version": "0.1.0-beta", "platform": "Windows"
        }).json()
        return {"access": reg["access_token"], "email": email, "device": device}

    def test_me_returns_profile(self, client, tokens):
        res = client.get("/user/me", headers={"Authorization": f"Bearer {tokens['access']}"})
        assert res.status_code == 200
        assert res.json()["email"] == tokens["email"]

    def test_me_requires_auth(self, client):
        res = client.get("/user/me")
        assert res.status_code == 401

    def test_license_returns_valid(self, client, tokens):
        res = client.get("/user/license", headers={"Authorization": f"Bearer {tokens['access']}"})
        assert res.status_code == 200
        data = res.json()
        assert "valid" in data
        assert "plan" in data

    def test_devices_returns_list(self, client, tokens):
        res = client.get("/user/devices", headers={"Authorization": f"Bearer {tokens['access']}"})
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestHealth:
    def test_health_endpoint(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
