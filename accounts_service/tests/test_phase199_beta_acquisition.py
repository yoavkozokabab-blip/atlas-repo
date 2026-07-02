"""Phase 199 — private beta acquisition (invite codes, funnel, launch readiness)."""
from __future__ import annotations

import os
import secrets
import sys

import pytest
from fastapi.testclient import TestClient

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_phase199.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-phase199-do-not-use-in-prod-32b")
os.environ.setdefault("ATLAS_INITIAL_ADMINS", "admin199@example.com")

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import UsageDaily, User
from accounts_service.rate_limit import reset_rate_limit_store


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    reset_rate_limit_store()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_phase199.db"):
        try:
            os.unlink("test_phase199.db")
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limit_store()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _profile():
    return {
        "currently_developer": True,
        "project_use": "work",
        "company_size": "11_50",
        "developer_experience": "3_5",
        "primary_role": "backend",
        "coding_tools": ["claude"],
        "repo_size": "medium",
        "atlas_help": ["planning_changes"],
        "company_name": "Acme",
        "languages_frameworks": "Python",
    }


def _register(client, email=None, invite_code=None):
    email = email or f"beta199_{secrets.token_hex(4)}@example.com"
    device = secrets.token_hex(16)
    payload = {
        "email": email,
        "password": "SecurePass1!",
        "confirm_password": "SecurePass1!",
        "device_id": device,
        "app_version": "0.1.0-beta",
        "platform": "test",
        "beta_profile": _profile(),
    }
    if invite_code:
        payload["invite_code"] = invite_code
    return client.post("/auth/register", json=payload), email, device


def _admin_token(client):
    res, email, device = _register(client)
    assert res.status_code == 201, res.text
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


def test_invite_code_create_and_register(client):
    token = _admin_token(client)
    created = client.post(
        "/admin/invites",
        json={"email": "invited@example.com", "max_uses": 1, "expires_days": 7},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    code = created.json()["code"]

    valid = client.post("/acquisition/validate-invite", json={"code": code})
    assert valid.status_code == 200
    assert valid.json()["valid"] is True

    res, email, _ = _register(client, email="invited@example.com", invite_code=code)
    assert res.status_code == 201

    again = client.post("/acquisition/validate-invite", json={"code": code})
    assert again.json()["valid"] is False


def test_invite_code_grants_immediate_beta_access(client):
    token = _admin_token(client)
    email = f"instant.{secrets.token_hex(4)}@example.com"
    created = client.post(
        "/admin/invites",
        json={"email": email, "max_uses": 1, "expires_days": 7},
        headers={"Authorization": f"Bearer {token}"},
    )
    code = created.json()["code"]
    res, _, device = _register(client, email=email, invite_code=code)
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["status"] == "beta"
    assert body["user"]["beta_flag"] is True

    lic = client.get(
        "/user/license",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert lic.status_code == 200
    assert lic.json()["valid"] is True
    assert lic.json()["plan"] == "beta"


def test_acquisition_funnel_and_launch_readiness(client):
    token = _admin_token(client)
    res, email, device = _register(client)
    assert res.status_code == 201
    user_id = res.json()["user"]["user_id"]
    user_token = res.json()["access_token"]

    client.post(
        "/acquisition/event",
        json={"stage": "waitlist_signup", "device_id": device},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    client.post(
        "/acquisition/event",
        json={"stage": "first_scan", "device_id": device},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    approve = client.post(
        f"/admin/users/{user_id}/approve-application",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert approve.status_code == 200

    fb = client.post(
        "/feedback",
        json={"category": "missing_feature", "message": "Need better graph navigation", "nps_score": 9},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert fb.status_code == 201
    assert fb.json()["sentiment"] == "positive"

    client.post(
        "/feedback",
        json={"category": "bug", "message": "Crash on large repo scan"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    db = SessionLocal()
    try:
        db.add(UsageDaily(
            user_id=user_id,
            device_id=device,
            date=__import__("datetime").date.today(),
            launches=2,
            scans=1,
        ))
        db.commit()
    finally:
        db.close()

    readiness = client.get("/admin/launch-readiness", headers={"Authorization": f"Bearer {token}"})
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["active_beta_users"] >= 1
    assert body["funnel_counts"]["registered"] >= 1
    assert body["funnel_counts"]["approved"] >= 1
    assert body["nps"]["nps_score"] == 100
    assert body["critical_bugs"] >= 1
    assert body["launch_verdict"]["verdict"] in ("strong_signal", "mixed_signal", "weak_signal")
    assert "headline" in body["launch_verdict"]


def test_feedback_admin_update_and_export(client):
    token = _admin_token(client)
    res, _, _ = _register(client)
    user_token = res.json()["access_token"]

    fb = client.post(
        "/feedback",
        json={"category": "general", "message": "Atlas is helpful for planning", "nps_score": 8},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    fid = fb.json()["feedback_id"]

    updated = client.patch(
        f"/admin/feedback/{fid}",
        json={"status": "reviewed"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "reviewed"

    export = client.get("/admin/export/beta-users", headers={"Authorization": f"Bearer {token}"})
    assert export.status_code == 200
    assert "users" in export.json()

    summary = client.get("/admin/interview-summary", headers={"Authorization": f"Bearer {token}"})
    assert summary.status_code == 200
    assert "by_category" in summary.json()
