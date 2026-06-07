"""Phase 186E regression tests for confirmed accounts beta blockers."""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_186e.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-186e")

from fastapi.testclient import TestClient

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import Device, License, Session as DBSession, User
from accounts_service.rate_limit import reset_rate_limit_store
from jarvis_desktop import accounts_client, server
from jarvis_desktop.data_paths import reset_desktop_data_dir_cache


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
def desktop_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    reset_desktop_data_dir_cache()
    yield Path(tmp_path)
    reset_desktop_data_dir_cache()


def _register(client: TestClient, *, email: str | None = None, device: str | None = None) -> Dict[str, Any]:
    email = email or f"phase186e_{secrets.token_hex(6)}@example.com"
    device = device or secrets.token_hex(16)
    res = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SecurePass1!",
            "device_id": device,
            "app_version": "0.1.0-beta",
            "platform": "test",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    data["_email"] = email
    data["_device"] = device
    return data


def _auth(data: Dict[str, Any]) -> Dict[str, str]:
    return {"Authorization": f"Bearer {data['access_token']}"}


def _service_call(client: TestClient):
    def _call(
        method: str,
        path: str,
        payload: Dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        res = client.request(method, path, json=payload, headers=headers)
        if res.status_code >= 400:
            try:
                body = res.json()
            except ValueError:
                body = {"detail": res.text}
            body["_http_status"] = res.status_code
            return body
        return res.json() if res.content else {}

    return _call


def _set_user_status(user_id: str, status: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).one()
        user.status = status
        db.commit()
    finally:
        db.close()


def _expire_license(user_id: str) -> None:
    db = SessionLocal()
    try:
        license_row = db.query(License).filter(License.user_id == user_id).one()
        license_row.status = "expired"
        license_row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        db.commit()
    finally:
        db.close()


def test_phase186e_device_revocation_invalidates_existing_access_token(client):
    user = _register(client)
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == user["_device"]).one()
        device.status = "revoked"
        session = db.query(DBSession).filter(DBSession.user_id == user["user"]["user_id"]).one()
        session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.revoked_reason = "device_revoked"
        db.commit()
    finally:
        db.close()

    profile = client.get("/user/me", headers=_auth(user))
    assert profile.status_code in (401, 403), profile.text
    refresh = client.post(
        "/auth/refresh",
        json={"refresh_token": user["refresh_token"], "device_id": user["_device"]},
    )
    assert refresh.status_code == 401


def test_phase186e_cross_account_device_id_reuse_rejected(client):
    reused_device = secrets.token_hex(16)
    _register(client, device=reused_device)

    second = client.post(
        "/auth/register",
        json={
            "email": f"phase186e_{secrets.token_hex(6)}@example.com",
            "password": "SecurePass1!",
            "device_id": reused_device,
            "app_version": "0.1.0-beta",
            "platform": "test",
        },
    )

    assert second.status_code == 403
    assert "already registered" in second.text


@pytest.mark.parametrize("status", ["banned", "suspended"])
def test_phase186e_desktop_state_denies_banned_and_suspended_users(client, desktop_tmp, monkeypatch, status):
    user = _register(client)
    monkeypatch.setattr(accounts_client, "_call", _service_call(client))
    accounts_client._persist_token_response(user)

    _set_user_status(user["user"]["user_id"], status)

    state = accounts_client.get_account_state()

    assert state["authenticated"] is False
    assert state["license"]["valid"] is False
    saved = json.loads((desktop_tmp / "accounts_state.json").read_text(encoding="utf-8"))
    assert "access_token" not in saved
    assert "refresh_token" not in saved


def test_phase186e_protected_workflows_require_valid_license(client, desktop_tmp, monkeypatch):
    monkeypatch.setattr(accounts_client, "_call", _service_call(client))

    status, payload = server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    assert status == 403
    assert payload["code"] == "account_required"

    user = _register(client)
    accounts_client._persist_token_response(user)
    _expire_license(user["user"]["user_id"])

    status, payload = server.dispatch("POST", "/api/planning/change", {"request": "change auth"})
    assert status == 403
    assert payload["code"] == "license_required"


def test_phase186e_analytics_rejects_unknown_event_type_secret_and_code(client):
    user = _register(client)
    base = {
        "device_id": user["_device"],
        "app_version": "0.1.0-beta",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "launches": 0,
        "scans": 0,
        "change_plans": 0,
        "debug_runs": 0,
        "what_breaks_runs": 0,
        "exports": 0,
        "estimated_tokens_saved": 0,
    }

    valid = client.post("/analytics/event", json={**base, "event_type": "heartbeat"}, headers=_auth(user))
    assert valid.status_code == 204

    for event_type in ("ghp_LEAK", "def x(): pass", "secret_prompt_export"):
        blocked = client.post("/analytics/event", json={**base, "event_type": event_type}, headers=_auth(user))
        assert blocked.status_code == 422


def test_phase186e_offline_grace_cache_tamper_rejected(client, desktop_tmp, monkeypatch):
    user = _register(client)
    monkeypatch.setattr(accounts_client, "_call", _service_call(client))
    accounts_client._persist_token_response(user)

    state_path = desktop_tmp / "accounts_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["license_checked_at"] = time.time()
    state["access_token_expires_at"] = time.time() + (30 * 24 * 3600)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        accounts_client,
        "_call",
        lambda *_args, **_kwargs: {"_offline": True, "detail": "accounts service unreachable"},
    )

    account_state = accounts_client.get_account_state()

    assert account_state["authenticated"] is False
    assert account_state["state_integrity_error"] is True
    assert account_state["license"]["status"] == "local_state_tampered"
