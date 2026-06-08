"""Phase 191 — registration reliability and admin intake."""
from __future__ import annotations

import os
import secrets
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_phase191.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-phase191-do-not-use-in-prod-32b")

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import AdminNotification, BetaProfile, User
from accounts_service.rate_limit import reset_rate_limit_store


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    reset_rate_limit_store()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_phase191.db"):
        try:
            os.unlink("test_phase191.db")
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limit_store()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _profile(**overrides):
    base = {
        "currently_developer": True,
        "project_use": "work",
        "company_size": "11_50",
        "developer_experience": "3_5",
        "primary_role": "backend",
        "coding_tools": ["claude"],
        "repo_size": "medium",
        "atlas_help": ["planning_changes"],
        "company_name": "Acme Labs",
        "languages_frameworks": "Python, TypeScript",
        "notes": "Interested in beta",
    }
    base.update(overrides)
    return base


def _register(client, email=None, password="SecurePass1!"):
    email = email or f"phase191_{secrets.token_hex(5)}@example.com"
    device = secrets.token_hex(16)
    res = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "confirm_password": password,
        "device_id": device,
        "app_version": "0.1.0-beta",
        "platform": "test",
        "beta_profile": _profile(),
    })
    return res, email, device


def _admin_token(client):
    reg, email, device = _register(client)
    assert reg.status_code == 201, reg.text
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).first()
        u.role = "superadmin"
        db.commit()
    login = client.post("/auth/login", json={
        "email": email,
        "password": "SecurePass1!",
        "device_id": device,
        "app_version": "0.1.0-beta",
        "platform": "test",
    })
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


class TestRegistrationReliability:
    def test_successful_submit_creates_account_profile_and_notification(self, client):
        res, email, _ = _register(client)
        assert res.status_code == 201, res.text
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email).first()
            assert user is not None
            assert user.status == "pending"
            profile = db.query(BetaProfile).filter(BetaProfile.user_id == user.user_id).first()
            assert profile is not None
            assert profile.primary_role == "backend"
            note = db.query(AdminNotification).filter(AdminNotification.user_id == user.user_id).first()
            assert note is not None
            assert note.email == email
            assert note.summary["company_name"] == "Acme Labs"

    def test_duplicate_submit_rejected(self, client):
        first, email, _ = _register(client)
        assert first.status_code == 201
        second, _, __ = _register(client, email=email)
        assert second.status_code == 409
        assert "already registered" in second.json()["detail"].lower()

    def test_pending_applications_list(self, client):
        _register(client)
        token = _admin_token(client)
        res = client.get("/admin/applications/pending", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        apps = res.json()
        assert isinstance(apps, list)
        assert len(apps) >= 1
        assert apps[0]["beta_profile"]["primary_role"]

    def test_admin_notification_created(self, client):
        res, email, _ = _register(client)
        assert res.status_code == 201
        token = _admin_token(client)
        notes = client.get("/admin/notifications?unread_only=true", headers={"Authorization": f"Bearer {token}"})
        assert notes.status_code == 200
        items = notes.json()
        assert any(n["email"] == email for n in items)

    def test_approve_application(self, client):
        res, _email, _ = _register(client)
        user_id = res.json()["user"]["user_id"]
        token = _admin_token(client)
        out = client.post(
            f"/admin/users/{user_id}/approve-application",
            json={"admin_notes": "Looks good"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert out.status_code == 200, out.text
        body = out.json()
        assert body["status"] == "beta"
        assert body["beta_flag"] is True

    def test_reject_application(self, client):
        res, _email, _ = _register(client)
        user_id = res.json()["user"]["user_id"]
        token = _admin_token(client)
        out = client.post(
            f"/admin/users/{user_id}/reject-application",
            json={"admin_notes": "Not a fit for this cohort"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert out.status_code == 200, out.text
        assert out.json()["status"] == "expired"


class TestDesktopRegisterProxy:
    def test_service_unavailable_response_shape(self):
        from jarvis_desktop import accounts_routes

        with patch("jarvis_desktop.accounts_service_runner.ensure_running", return_value=False):
            out = accounts_routes.accounts_register({
                "email": "offline@example.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
                "beta_profile": _profile(),
            }, {})
        assert out["ok"] is False
        assert out["code"] == "service_unavailable"
        assert out["submitted"] is False
        assert "has not been submitted" in out["detail"].lower()

    def test_duplicate_email_proxy_code(self):
        from jarvis_desktop import accounts_routes

        calls = {"n": 0}

        def fake_register(**_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return {"access_token": "tok", "user": {"user_id": "u1", "email": "a@example.com"}, "license": {}}
            return {"_http_status": 409, "detail": "Email already registered."}

        with patch("jarvis_desktop.accounts_service_runner.ensure_running", return_value=True):
            with patch("jarvis_desktop.accounts_client.register", side_effect=fake_register):
                first = accounts_routes.accounts_register({
                    "email": "dup@example.com",
                    "password": "SecurePass1!",
                    "confirm_password": "SecurePass1!",
                    "beta_profile": _profile(),
                }, {})
                second = accounts_routes.accounts_register({
                    "email": "dup@example.com",
                    "password": "SecurePass1!",
                    "confirm_password": "SecurePass1!",
                    "beta_profile": _profile(),
                }, {})
        assert first["ok"] is True
        assert second["ok"] is False
        assert second["code"] == "duplicate_email"
        assert second["submitted"] is False
