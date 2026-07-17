"""Phase 186C — accounts beta safety fixes."""
from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import jwt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_186c.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-186c-do-not-use-in-prod-32b")
os.environ.setdefault("ATLAS_ACCOUNTS_DATA_DIR", os.path.join(_ROOT, ".phase186c_accounts_data"))

from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import Session as DBSession
from accounts_service.models import User
from accounts_service.security import hash_token
from accounts_service.rate_limit import reset_rate_limit_store


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    reset_rate_limit_store()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    db_file = "test_accounts_186c.db"
    if os.path.exists(db_file):
        try:
            os.unlink(db_file)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    reset_rate_limit_store()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client: TestClient) -> dict:
    email = f"user_{secrets.token_hex(5)}@example.com"
    device = secrets.token_hex(16)
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


class TestEnvironmentJwtSecret:
    def test_secret_file_is_not_a_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path / "authdata"))
        monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
        monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)

        from accounts_service.jwt_secret import load_jwt_secret
        with pytest.raises(RuntimeError, match="required"):
            load_jwt_secret()

    def test_login_token_valid_after_simulated_restart(self, client):
        from accounts_service import config
        from accounts_service.security import decode_access_token

        reg = _register(client)
        token = reg["access_token"]
        payload = decode_access_token(token)
        assert payload["sub"] == reg["user"]["user_id"]
        # Simulated restart: secret loader returns the same configured secret.
        from accounts_service.jwt_secret import load_jwt_secret

        assert load_jwt_secret() == config.JWT_SECRET
        assert decode_access_token(token)["sub"] == reg["user"]["user_id"]

    def test_secret_not_exposed_by_health_or_config(self, client):
        from accounts_service.config import JWT_SECRET

        res = client.get("/health")
        assert res.status_code == 200
        blob = json.dumps(res.json())
        assert JWT_SECRET not in blob
        assert "jwt_secret" not in blob.lower()


class TestFeedbackRedaction:
    def test_api_key_redacted_in_stored_feedback(self, client):
        res = client.post("/feedback", json={
            "message": "Broken export api_key=LEAK_ME_123 please fix",
            "category": "bug",
        })
        assert res.status_code == 201
        body = res.json()
        assert "LEAK_ME_123" not in body["message_redacted"]

    def test_windows_path_redacted(self, client):
        res = client.post("/feedback", json={
            "message": "Crash in C:\\Users\\dev\\project\\main.py during scan",
        })
        assert res.status_code == 201
        assert "C:\\Users" not in res.json()["message_redacted"]
        assert "[path-redacted]" in res.json()["message_redacted"]

    def test_unix_path_redacted(self, client):
        res = client.post("/feedback", json={
            "message": "Fails reading /home/dev/project/src/app.py",
        })
        assert res.status_code == 201
        assert "/home/dev" not in res.json()["message_redacted"]
        assert "[path-redacted]" in res.json()["message_redacted"]


class TestRefreshTokenStorage:
    def test_db_stores_hash_not_raw_refresh_token(self, client):
        reg = _register(client)
        raw = reg["refresh_token"]
        with SessionLocal() as db:
            row = db.query(DBSession).filter(DBSession.user_id == reg["user"]["user_id"]).first()
            assert row is not None
            assert row.refresh_hash == hash_token(raw)
            assert row.refresh_hash != raw

    def test_support_bundle_redacts_refresh_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        from jarvis_desktop.data_paths import desktop_data_dir
        from jarvis_desktop.install_support import export_support_bundle

        state_path = os.path.join(desktop_data_dir(), "accounts_state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        raw_refresh = "a" * 64
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump({"refresh_token": raw_refresh, "access_token": "eyJ.test.token"}, fh)

        bundle = export_support_bundle()
        import io
        import zipfile

        raw = __import__("base64").b64decode(bundle["content_base64"])
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            redacted_blob = ""
            for name in zf.namelist():
                if "accounts_state_redacted" in name:
                    redacted_blob = zf.read(name).decode("utf-8")
            assert redacted_blob
            assert raw_refresh not in redacted_blob


class TestTokenClaimTrust:
    def _auth_header(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def test_forged_jwt_rejected(self, client):
        token = jwt.encode(
            {
                "sub": "fake-user",
                "email": "fake@test.dev",
                "role": "superadmin",
                "beta": True,
                "plan": "free",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "aud": "atlas-api",
                "iss": "atlas-auth",
            },
            "wrong-secret-not-the-real-one-32bytes",
            algorithm="HS256",
        )
        res = client.get("/user/me", headers=self._auth_header(token))
        assert res.status_code == 401

    def test_expired_jwt_rejected(self, client):
        from accounts_service.config import JWT_SECRET

        token = jwt.encode(
            {
                "sub": "expired-user",
                "email": "exp@test.dev",
                "role": "user",
                "beta": False,
                "plan": "free",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                "aud": "atlas-api",
                "iss": "atlas-auth",
            },
            JWT_SECRET,
            algorithm="HS256",
        )
        res = client.get("/user/me", headers=self._auth_header(token))
        assert res.status_code == 401

    def test_modified_role_claim_rejected(self, client):
        from accounts_service.config import JWT_SECRET

        reg = _register(client)
        parts = reg["access_token"].split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
        payload["role"] = "superadmin"
        header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
        tampered = jwt.encode(payload, "wrong-secret-not-the-real-one-32bytes", algorithm="HS256", headers=header)
        res = client.get("/user/me", headers=self._auth_header(tampered))
        assert res.status_code == 401


class TestAdminActionValidation:
    def _superadmin_headers(self, client) -> dict:
        reg = _register(client)
        with SessionLocal() as db:
            user = db.query(User).filter(User.user_id == reg["user"]["user_id"]).first()
            user.role = "superadmin"
            db.commit()
        login = client.post("/auth/login", json={
            "email": reg["_email"],
            "password": "SecurePass1!",
            "device_id": reg["_device"],
            "app_version": "0.1.0-beta",
            "platform": "test",
        })
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_invalid_status_rejected(self, client):
        admin_hdr = self._superadmin_headers(client)
        target = _register(client)
        uid = target["user"]["user_id"]
        res = client.patch(f"/admin/users/{uid}", headers=admin_hdr, json={"status": "not-a-status"})
        assert res.status_code == 422

    def test_non_superadmin_cannot_unban(self, client):
        super_hdr = self._superadmin_headers(client)
        target = _register(client)
        uid = target["user"]["user_id"]
        ban = client.patch(f"/admin/users/{uid}", headers=super_hdr, json={"status": "banned"})
        assert ban.status_code == 200

        admin_reg = _register(client)
        with SessionLocal() as db:
            admin_user = db.query(User).filter(User.user_id == admin_reg["user"]["user_id"]).first()
            admin_user.role = "admin"
            db.commit()
        admin_login = client.post("/auth/login", json={
            "email": admin_reg["_email"],
            "password": "SecurePass1!",
            "device_id": admin_reg["_device"],
            "app_version": "0.1.0-beta",
            "platform": "test",
        })
        assert admin_login.status_code == 200, admin_login.text
        admin_hdr = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        res = client.patch(f"/admin/users/{uid}", headers=admin_hdr, json={"status": "active"})
        assert res.status_code == 403

    def test_audit_log_written_on_status_change(self, client):
        admin_hdr = self._superadmin_headers(client)
        target = _register(client)
        uid = target["user"]["user_id"]
        res = client.patch(f"/admin/users/{uid}", headers=admin_hdr, json={"status": "suspended"})
        assert res.status_code == 200
        audit = client.get("/admin/audit-log", headers=admin_hdr)
        assert audit.status_code == 200
        actions = [row["action"] for row in audit.json()]
        assert "update_user" in actions


class TestRateLimiterCleanup:
    def test_old_keys_pruned_active_keys_retained(self):
        from accounts_service import rate_limit as rl

        rl._store._windows.clear()
        assert rl.check_rate_limit("login:1.2.3.4", max_calls=5, window_seconds=900)
        dq = rl._store._windows["login:1.2.3.4"]
        dq.clear()
        dq.append(0.0)

        removed = rl.prune_rate_limit_keys(max_idle_seconds=1)
        assert removed >= 1
        assert "login:1.2.3.4" not in rl._store._windows

        assert rl.check_rate_limit("login:9.9.9.9", max_calls=5, window_seconds=900)
        assert "login:9.9.9.9" in rl._store._windows
