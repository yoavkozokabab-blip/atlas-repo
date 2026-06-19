"""Phase 188 - beta profile account storage and admin privacy tests."""
from __future__ import annotations

import json
import os
import secrets
import sys
from typing import Any, Dict

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_188.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-188")

from fastapi.testclient import TestClient

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import BetaProfile, Session as DBSession, User
from accounts_service.rate_limit import reset_rate_limit_store
from jarvis_desktop import accounts_routes


BETA_PROFILE: Dict[str, Any] = {
    "currently_developer": True,
    "project_use": "both",
    "company_size": "2_10",
    "developer_experience": "3_5",
    "primary_role": "full_stack",
    "coding_tools": ["claude", "codex"],
    "languages_frameworks": "Python, TypeScript",
    "repo_size": "medium",
    "atlas_help": ["planning_changes", "what_breaks"],
    "notes": "Looking for safer change planning.",
}


@pytest.fixture(autouse=True)
def _reset_db():
    reset_rate_limit_store()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _device() -> str:
    return secrets.token_hex(16)


def _register(client: TestClient, *, email: str | None = None, profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
    email = email or f"phase188_{secrets.token_hex(6)}@example.com"
    res = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass1!",
            "confirm_password": "SecurePass1!",
            "device_id": _device(),
            "app_version": "0.1.0-beta",
            "platform": "test",
            "beta_profile": profile if profile is not None else BETA_PROFILE,
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    data["_email"] = email
    return data


def _auth(data: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {data['access_token']}"}


def _make_admin(user_id: str, role: str = "admin") -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.user_id == user_id).one()
        user.role = role
        db.commit()


def test_phase188_register_stores_beta_profile_and_keeps_account_pending(client):
    reg = _register(client)

    assert reg["user"]["status"] == "pending"
    assert reg["user"]["beta_profile"]["project_use"] == "both"
    assert reg["user"]["beta_profile"]["coding_tools"] == ["claude", "codex"]

    license_check = client.get("/user/license", headers=_auth(reg))
    assert license_check.status_code == 200
    assert license_check.json()["valid"] is False
    assert license_check.json()["status"] == "pending"
    assert license_check.json()["message"] == "Your account was created and is waiting for beta approval."

    with SessionLocal() as db:
        profile = db.query(BetaProfile).filter(BetaProfile.user_id == reg["user"]["user_id"]).one()
        assert profile.company_name is None
        assert profile.primary_role == "full_stack"
        assert profile.atlas_help == ["planning_changes", "what_breaks"]


def test_phase188_optional_company_name_may_be_empty(client):
    profile = {**BETA_PROFILE, "company_name": ""}
    reg = _register(client, profile=profile)

    with SessionLocal() as db:
        saved = db.query(BetaProfile).filter(BetaProfile.user_id == reg["user"]["user_id"]).one()
        assert saved.company_name is None


def test_phase188_profile_rejects_secrets_code_and_paths(client):
    for field, value in (
        ("notes", "api_key=LEAK"),
        ("notes", "def leak(): pass"),
        ("languages_frameworks", "C:\\Users\\name\\secret"),
        ("company_name", "/home/name/secret"),
    ):
        profile = {**BETA_PROFILE, field: value}
        res = client.post(
            "/auth/register",
            json={
                "email": f"phase188_bad_{secrets.token_hex(6)}@example.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
                "device_id": _device(),
                "app_version": "0.1.0-beta",
                "platform": "test",
                "beta_profile": profile,
            },
        )
        assert res.status_code == 422


def test_phase188_admin_can_view_profile_without_password_or_token_hashes(client):
    admin = _register(client, email=f"phase188_admin_{secrets.token_hex(6)}@example.com")
    _make_admin(admin["user"]["user_id"], role="admin")
    applicant = _register(client)

    users = client.get("/admin/users?limit=200", headers=_auth(admin))

    assert users.status_code == 200, users.text
    body = users.json()
    row = next(user for user in body if user["email"] == applicant["_email"])
    assert row["beta_profile"]["developer_experience"] == "3_5"
    assert row["beta_profile"]["primary_role"] == "full_stack"
    assert row["license"]["plan"] == "free"
    assert row["device_count"] == 1

    serialized = json.dumps(row).lower()
    assert "password_hash" not in serialized
    assert "refresh_hash" not in serialized
    assert "refresh_token" not in serialized
    assert "access_token" not in serialized

    with SessionLocal() as db:
        assert db.query(DBSession).filter(DBSession.user_id == applicant["user"]["user_id"]).first() is not None


def test_phase188_desktop_register_validates_email_password_and_required_profile(monkeypatch):
    calls: list[Dict[str, Any]] = []

    def fake_register(**kwargs):
        calls.append(kwargs)
        return {"access_token": "x", "refresh_token": "y", "user": {"email": kwargs["email"]}}

    monkeypatch.setattr(accounts_routes.accounts_client, "register", fake_register)

    bad_email = accounts_routes.accounts_register(
        {"email": "bad", "password": "SecurePass1!", "confirm_password": "SecurePass1!", "beta_profile": BETA_PROFILE},
        {},
    )
    assert bad_email["ok"] is False
    assert bad_email["error"] == "Enter a valid email address."

    mismatch = accounts_routes.accounts_register(
        {
            "email": "phase188@example.com",
            "password": "SecurePass1!",
            "confirm_password": "Different1!",
            "beta_profile": BETA_PROFILE,
        },
        {},
    )
    assert mismatch["ok"] is False
    assert mismatch["error"] == "Passwords do not match."

    missing_profile = accounts_routes.accounts_register(
        {"email": "phase188@example.com", "password": "SecurePass1!", "confirm_password": "SecurePass1!"},
        {},
    )
    assert missing_profile["ok"] is False
    assert "beta profile" in missing_profile["error"].lower()

    ok = accounts_routes.accounts_register(
        {
            "email": "phase188@example.com",
            "password": "SecurePass1!",
            "confirm_password": "SecurePass1!",
            "beta_profile": {**BETA_PROFILE, "company_name": ""},
        },
        {},
    )
    assert ok["ok"] is True
    assert calls[0]["beta_profile"]["company_name"] == ""


def test_phase188_signin_errors_do_not_leak_account_existence(client):
    """Anti-enumeration (Phase 186D): unknown-email and wrong-password logins must
    return the SAME status and the SAME generic message, so an attacker cannot use
    the error to discover which emails have accounts."""
    generic = "Invalid email or password."

    unknown = client.post(
        "/auth/login",
        json={
            "email": "missing@example.com",
            "password": "SecurePass1!",
            "device_id": _device(),
            "app_version": "0.1.0-beta",
            "platform": "test",
        },
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == generic

    reg = _register(client)
    wrong = client.post(
        "/auth/login",
        json={
            "email": reg["_email"],
            "password": "WrongPass1!",
            "device_id": _device(),
            "app_version": "0.1.0-beta",
            "platform": "test",
        },
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == generic
    # The two responses must be indistinguishable.
    assert unknown.json()["detail"] == wrong.json()["detail"]
