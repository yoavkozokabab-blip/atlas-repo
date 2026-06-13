"""Phase 197 - paid license lifecycle enforcement."""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_197.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-197")

from fastapi.testclient import TestClient

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import AdminAuditLog, License, User
from accounts_service.rate_limit import reset_rate_limit_store


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


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _register(client: TestClient, *, email: str | None = None, device: str | None = None) -> Dict[str, Any]:
    email = email or f"phase197_{secrets.token_hex(6)}@example.com"
    device = device or secrets.token_hex(16)
    res = client.post("/auth/register", json={
        "email": email,
        "password": "SecurePass1!",
        "device_id": device,
        "app_version": "0.1.0-beta",
        "platform": "test",
    })
    assert res.status_code == 201, res.text
    data = res.json()
    data["_email"] = email
    data["_device"] = device
    return data


def _auth(data: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {data['access_token']}"}


def _activate_paid_license(db_session, user_id: str, *, status: str, expires_at=None) -> None:
    user = db_session.query(User).filter(User.user_id == user_id).one()
    user.status = "active"
    lic = db_session.query(License).filter(License.user_id == user_id).one()
    lic.plan = "pro"
    lic.status = status
    lic.max_devices = 3
    lic.expires_at = expires_at
    db_session.commit()


def test_phase197_trial_license_valid_only_until_expiry(client, db):
    reg = _register(client)
    future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    _activate_paid_license(db, reg["user"]["user_id"], status="trial", expires_at=future)

    ok = client.get("/user/license", headers=_auth(reg))
    assert ok.status_code == 200
    body = ok.json()
    assert body["valid"] is True
    assert body["plan"] == "pro"
    assert body["status"] == "trial"
    assert body["beta_features"] is True

    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    _activate_paid_license(db, reg["user"]["user_id"], status="trial", expires_at=past)

    expired = client.get("/user/license", headers=_auth(reg))
    assert expired.status_code == 200
    assert expired.json()["valid"] is False
    assert expired.json()["status"] == "expired"


@pytest.mark.parametrize("status", ["past_due", "canceled", "cancelled", "suspended"])
def test_phase197_paid_inactive_statuses_are_denied(client, db, status):
    reg = _register(client)
    _activate_paid_license(db, reg["user"]["user_id"], status=status)

    res = client.get("/user/license", headers=_auth(reg))
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
    assert body["plan"] == "pro"
    assert body["status"] == status
    assert body["message"]


def test_phase197_trial_without_expiry_is_denied(client, db):
    reg = _register(client)
    _activate_paid_license(db, reg["user"]["user_id"], status="trial", expires_at=None)

    res = client.get("/user/license", headers=_auth(reg))
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
    assert body["status"] == "trial_missing_expiry"


def test_phase197_admin_can_set_license_status_and_audit(client, db):
    admin = _register(client, email="phase197-admin@example.com")
    target = _register(client, email="phase197-target@example.com")

    admin_user = db.query(User).filter(User.user_id == admin["user"]["user_id"]).one()
    admin_user.status = "active"
    admin_user.role = "admin"
    target_user = db.query(User).filter(User.user_id == target["user"]["user_id"]).one()
    target_user.status = "active"
    db.commit()

    res = client.patch(
        f"/admin/users/{target['user']['user_id']}",
        headers=_auth(admin),
        json={"plan": "pro", "license_status": "past_due", "max_devices": 3},
    )
    assert res.status_code == 200, res.text
    assert res.json()["license"]["plan"] == "pro"
    assert res.json()["license"]["status"] == "past_due"

    lic = db.query(License).filter(License.user_id == target["user"]["user_id"]).one()
    assert lic.status == "past_due"
    audit = db.query(AdminAuditLog).filter(AdminAuditLog.action == "update_user").one()
    assert audit.metadata_["after"]["license"]["status"] == "past_due"
