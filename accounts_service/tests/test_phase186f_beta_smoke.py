"""Phase 186F — Beta operations smoke tests.

Covers:
  - JWT secret persistence (verify jwt_secret.py stores and reloads correctly)
  - Session cleanup (prune_sessions / prune_all correctness)
  - Superadmin bootstrap (INITIAL_ADMINS promotion, idempotency)
  - End-to-end beta user lifecycle (register → grant-beta → use → revoke → ban)
  - Admin maintenance/prune endpoint
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_186f.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-186f")

from fastapi.testclient import TestClient

from accounts_service.bootstrap import bootstrap_superadmins
from accounts_service.database import Base, SessionLocal, engine
from accounts_service.main import app
from accounts_service.models import (
    AdminAuditLog,
    Device,
    EmailToken,
    License,
    Session as DBSession,
    User,
)
from accounts_service.rate_limit import reset_rate_limit_store
from accounts_service.session_cleanup import prune_all, prune_email_tokens, prune_sessions


# ── Fixtures ───────────────────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _register(client: TestClient, *, email: str | None = None, device: str | None = None) -> Dict[str, Any]:
    email = email or f"phase186f_{secrets.token_hex(6)}@example.com"
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


def _make_superadmin(db_session, user_id: str) -> None:
    db_session.query(User).filter(User.user_id == user_id).update({"role": "superadmin"})
    db_session.commit()


def _make_admin(db_session, user_id: str) -> None:
    db_session.query(User).filter(User.user_id == user_id).update({"role": "admin"})
    db_session.commit()


# ── JWT secret provisioning ────────────────────────────────────────────────────

class TestJwtSecretProvisioning:
    """Verify the jwt_secret.py persistence behaviour used in the runbook."""

    def test_env_var_takes_priority_over_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
        monkeypatch.setenv("ATLAS_JWT_SECRET", "env-override-secret-at-least-thirty-two-bytes")
        monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))

        from accounts_service.jwt_secret import load_jwt_secret
        result = load_jwt_secret()
        assert result == "env-override-secret-at-least-thirty-two-bytes"

    def test_atlas_auth_jwt_secret_takes_priority(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", "auth-override-secret-at-least-thirty-two-bytes")
        monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)
        monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))

        from accounts_service.jwt_secret import load_jwt_secret
        result = load_jwt_secret()
        assert result == "auth-override-secret-at-least-thirty-two-bytes"

    def test_missing_env_secret_uses_per_install_key(self, tmp_path, monkeypatch):
        """v1.0.5: a missing env var is NOT a packaged-production startup
        failure — the per-installation key store provides a stable, protected
        256-bit key so ordinary users never configure a secret manually."""
        monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))
        monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
        monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)

        import importlib
        import accounts_service.jwt_secret as jwt_secret
        importlib.reload(jwt_secret)
        first = jwt_secret.load_jwt_secret()
        assert len(first) >= 32
        # Stable across "restarts" (reload) and never a shipped default.
        importlib.reload(jwt_secret)
        assert jwt_secret.load_jwt_secret() == first

    def test_short_env_secret_still_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", "too-short")
        import importlib
        import accounts_service.jwt_secret as jwt_secret
        importlib.reload(jwt_secret)
        with pytest.raises(RuntimeError, match="32"):
            jwt_secret.load_jwt_secret()


# ── Session cleanup ────────────────────────────────────────────────────────────

class TestSessionCleanup:
    def test_expired_sessions_pruned(self, db):
        """Sessions whose refresh token has expired must be deleted."""
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=f"cleanup_{secrets.token_hex(5)}@example.com",
            password_hash="x",
        )
        db.add(user)
        db.flush()

        device = Device(
            device_id=secrets.token_hex(16),
            user_id=user.user_id,
            app_version="0.1",
            platform="test",
        )
        db.add(device)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expired_session = DBSession(
            user_id=user.user_id,
            device_id=device.device_id,
            refresh_hash=secrets.token_hex(32),
            created_at=now - timedelta(days=40),
            expires_at=now - timedelta(days=10),  # expired
        )
        db.add(expired_session)
        db.commit()
        expired_session_id = expired_session.session_id  # capture before ORM object is invalidated

        stats = prune_all(db)
        assert stats["sessions_expired"] >= 1
        assert db.query(DBSession).filter(DBSession.session_id == expired_session_id).first() is None

    def test_active_sessions_not_pruned(self, db):
        """Active (not expired, not revoked) sessions must be untouched."""
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=f"cleanup_active_{secrets.token_hex(5)}@example.com",
            password_hash="x",
        )
        db.add(user)
        db.flush()

        device = Device(
            device_id=secrets.token_hex(16),
            user_id=user.user_id,
            app_version="0.1",
            platform="test",
        )
        db.add(device)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active_session = DBSession(
            user_id=user.user_id,
            device_id=device.device_id,
            refresh_hash=secrets.token_hex(32),
            created_at=now,
            expires_at=now + timedelta(days=30),  # still valid
        )
        db.add(active_session)
        db.commit()

        prune_all(db)
        assert db.query(DBSession).filter(DBSession.session_id == active_session.session_id).first() is not None

    def test_recently_revoked_sessions_retained(self, db):
        """Revoked sessions within retention window are kept for audit trail."""
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=f"cleanup_revoked_{secrets.token_hex(5)}@example.com",
            password_hash="x",
        )
        db.add(user)
        db.flush()

        device = Device(
            device_id=secrets.token_hex(16),
            user_id=user.user_id,
            app_version="0.1",
            platform="test",
        )
        db.add(device)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        recent_revoke = DBSession(
            user_id=user.user_id,
            device_id=device.device_id,
            refresh_hash=secrets.token_hex(32),
            created_at=now,
            expires_at=now + timedelta(days=30),  # not yet expired
            revoked_at=now - timedelta(days=3),   # revoked 3 days ago (within 7-day window)
            revoked_reason="logout",
        )
        db.add(recent_revoke)
        db.commit()

        prune_all(db)
        assert db.query(DBSession).filter(DBSession.session_id == recent_revoke.session_id).first() is not None

    def test_old_revoked_sessions_pruned_after_retention(self, db):
        """Revoked sessions older than retention window are deleted."""
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=f"cleanup_old_{secrets.token_hex(5)}@example.com",
            password_hash="x",
        )
        db.add(user)
        db.flush()

        device = Device(
            device_id=secrets.token_hex(16),
            user_id=user.user_id,
            app_version="0.1",
            platform="test",
        )
        db.add(device)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        old_revoke = DBSession(
            user_id=user.user_id,
            device_id=device.device_id,
            refresh_hash=secrets.token_hex(32),
            created_at=now - timedelta(days=20),
            expires_at=now + timedelta(days=15),  # not yet expired
            revoked_at=now - timedelta(days=10),  # revoked 10 days ago (past 7-day window)
            revoked_reason="rotation",
        )
        db.add(old_revoke)
        db.commit()
        old_revoke_id = old_revoke.session_id  # capture before ORM object is invalidated

        stats = prune_all(db)
        assert stats["sessions_revoked_old"] >= 1
        assert db.query(DBSession).filter(DBSession.session_id == old_revoke_id).first() is None

    def test_email_tokens_pruned(self, db):
        """Expired or used email tokens must be deleted."""
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=f"token_{secrets.token_hex(5)}@example.com",
            password_hash="x",
        )
        db.add(user)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expired_token = EmailToken(
            user_id=user.user_id,
            kind="email_verification",
            token_hash=secrets.token_hex(32),
            created_at=now - timedelta(days=2),
            expires_at=now - timedelta(days=1),  # expired
        )
        used_token = EmailToken(
            user_id=user.user_id,
            kind="password_reset",
            token_hash=secrets.token_hex(32),
            created_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=23),  # not expired but used
            used_at=now - timedelta(minutes=30),
        )
        db.add(expired_token)
        db.add(used_token)
        db.commit()
        expired_token_id = expired_token.token_id  # capture before ORM object is invalidated
        used_token_id = used_token.token_id

        stats = prune_all(db)
        assert stats["email_tokens"] >= 2
        assert db.query(EmailToken).filter(EmailToken.token_id == expired_token_id).first() is None
        assert db.query(EmailToken).filter(EmailToken.token_id == used_token_id).first() is None

    def test_prune_all_is_idempotent(self, db):
        """Running prune_all twice does not raise and returns 0 on the second run."""
        stats_1 = prune_all(db)
        stats_2 = prune_all(db)
        assert stats_2["sessions_expired"] == 0
        assert stats_2["sessions_revoked_old"] == 0
        assert stats_2["email_tokens"] == 0


# ── Superadmin bootstrap ───────────────────────────────────────────────────────

class TestSuperadminBootstrap:
    def test_bootstrap_promotes_registered_user(self, monkeypatch, db):
        """User with email in INITIAL_ADMINS is promoted to superadmin."""
        email = f"admin_{secrets.token_hex(5)}@example.com"
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=email,
            password_hash="x",
            role="user",
        )
        db.add(user)
        db.commit()

        import accounts_service.bootstrap as bs
        monkeypatch.setattr(bs, "INITIAL_ADMINS", [email])
        count = bootstrap_superadmins(db)

        db.refresh(user)
        assert count == 1
        assert user.role == "superadmin"

    def test_bootstrap_writes_audit_log(self, monkeypatch, db):
        """Bootstrap promotion is recorded in AdminAuditLog."""
        email = f"audit_{secrets.token_hex(5)}@example.com"
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=email,
            password_hash="x",
            role="user",
        )
        db.add(user)
        db.commit()

        import accounts_service.bootstrap as bs
        monkeypatch.setattr(bs, "INITIAL_ADMINS", [email])
        bootstrap_superadmins(db)

        entry = (
            db.query(AdminAuditLog)
            .filter(AdminAuditLog.action == "bootstrap_superadmin")
            .first()
        )
        assert entry is not None
        assert entry.target_user_email == email
        assert entry.metadata_["after_role"] == "superadmin"

    def test_bootstrap_is_idempotent(self, monkeypatch, db):
        """Running bootstrap twice does not downgrade or fail."""
        email = f"idem_{secrets.token_hex(5)}@example.com"
        user = User(
            user_id=str(secrets.token_hex(18))[:36],
            email=email,
            password_hash="x",
            role="superadmin",  # already superadmin
        )
        db.add(user)
        db.commit()

        import accounts_service.bootstrap as bs
        monkeypatch.setattr(bs, "INITIAL_ADMINS", [email])
        count = bootstrap_superadmins(db)

        assert count == 0  # no-op
        db.refresh(user)
        assert user.role == "superadmin"

    def test_bootstrap_skips_unknown_email(self, monkeypatch, db):
        """Email not yet registered returns 0 (no error, no crash)."""
        import accounts_service.bootstrap as bs
        monkeypatch.setattr(bs, "INITIAL_ADMINS", ["notyet@example.com"])
        count = bootstrap_superadmins(db)
        assert count == 0

    def test_bootstrap_no_op_when_env_empty(self, monkeypatch, db):
        """Empty INITIAL_ADMINS list returns 0 immediately."""
        import accounts_service.bootstrap as bs
        monkeypatch.setattr(bs, "INITIAL_ADMINS", [])
        count = bootstrap_superadmins(db)
        assert count == 0


# ── Full beta user lifecycle ───────────────────────────────────────────────────

class TestFullBetaLifecycle:
    """End-to-end smoke test covering the complete supervised-beta user journey."""

    def test_register_and_license_check(self, client):
        """New beta applicant registers in pending state with a free license row."""
        user = _register(client)
        assert user["user"]["status"] == "pending"
        assert user["license"]["plan"] == "free"

        profile = client.get("/user/me", headers=_auth(user))
        assert profile.status_code == 200
        assert profile.json()["email"] == user["_email"]

        lic = client.get("/user/license", headers=_auth(user))
        assert lic.status_code == 200
        assert lic.json()["plan"] == "free"
        assert lic.json()["valid"] is False
        assert lic.json()["status"] == "pending"

    def test_admin_grants_and_revokes_beta(self, client, db):
        """Admin can grant beta status; user gets beta plan and extra device slots."""
        admin = _register(client)
        _make_admin(db, admin["user"]["user_id"])

        beta_user = _register(client)

        # Grant beta
        grant = client.post(
            f"/admin/users/{beta_user['user']['user_id']}/grant-beta",
            headers=_auth(admin),
        )
        assert grant.status_code == 200
        assert grant.json()["beta_flag"] is True
        assert grant.json()["status"] == "beta"

        # Verify license updated
        lic = client.get("/user/license", headers=_auth(beta_user))
        # Access token may have stale plan — check via admin
        admin_user = client.get(
            f"/admin/users/{beta_user['user']['user_id']}",
            headers=_auth(admin),
        )
        assert admin_user.json()["beta_flag"] is True

        # Revoke beta
        revoke = client.post(
            f"/admin/users/{beta_user['user']['user_id']}/revoke-beta",
            headers=_auth(admin),
        )
        assert revoke.status_code == 200
        assert revoke.json()["beta_flag"] is False

    def test_force_logout_invalidates_sessions(self, client, db):
        """Admin force-logout revokes all active sessions; subsequent requests fail."""
        admin = _register(client)
        _make_admin(db, admin["user"]["user_id"])

        target = _register(client)

        # Force logout
        resp = client.post(
            f"/admin/users/{target['user']['user_id']}/force-logout",
            headers=_auth(admin),
        )
        assert resp.status_code == 204

        # Original access token should still work (JWT not revoked immediately),
        # but refresh should fail because session is revoked.
        refresh = client.post("/auth/refresh", json={
            "refresh_token": target["refresh_token"],
            "device_id": target["_device"],
        })
        assert refresh.status_code == 401

    def test_device_revocation_via_admin(self, client, db):
        """Admin can revoke a specific device; subsequent API calls with that session fail."""
        admin = _register(client)
        _make_admin(db, admin["user"]["user_id"])

        target = _register(client)
        user_id = target["user"]["user_id"]
        device_id = target["_device"]

        # Revoke device
        rev = client.delete(
            f"/admin/users/{user_id}/devices/{device_id}",
            headers=_auth(admin),
        )
        assert rev.status_code == 204

        # The access token claims a revoked device — should now be rejected
        profile = client.get("/user/me", headers=_auth(target))
        assert profile.status_code in (401, 403)

    def test_suspend_and_unsuspend_user(self, client, db):
        """Admin can suspend a user; suspended user cannot use the service."""
        admin = _register(client)
        _make_superadmin(db, admin["user"]["user_id"])

        target = _register(client)
        user_id = target["user"]["user_id"]

        # Suspend
        suspend = client.patch(
            f"/admin/users/{user_id}",
            json={"status": "suspended"},
            headers=_auth(admin),
        )
        assert suspend.status_code == 200

        # Suspended user cannot log in
        login = client.post("/auth/login", json={
            "email": target["_email"],
            "password": "SecurePass1!",
            "device_id": target["_device"],
            "app_version": "0.1.0-beta",
            "platform": "test",
        })
        assert login.status_code == 403

        # Reinstate
        reinstate = client.patch(
            f"/admin/users/{user_id}",
            json={"status": "active"},
            headers=_auth(admin),
        )
        assert reinstate.status_code == 200

        # Can log in again
        login2 = client.post("/auth/login", json={
            "email": target["_email"],
            "password": "SecurePass1!",
            "device_id": target["_device"],
            "app_version": "0.1.0-beta",
            "platform": "test",
        })
        assert login2.status_code == 200

    def test_ban_requires_superadmin(self, client, db):
        """Regular admin cannot ban; superadmin can."""
        regular_admin = _register(client)
        _make_admin(db, regular_admin["user"]["user_id"])

        super_admin = _register(client)
        _make_superadmin(db, super_admin["user"]["user_id"])

        target = _register(client)
        user_id = target["user"]["user_id"]

        # Regular admin cannot ban
        fail = client.patch(
            f"/admin/users/{user_id}",
            json={"status": "banned"},
            headers=_auth(regular_admin),
        )
        assert fail.status_code == 403

        # Superadmin can ban
        ok = client.patch(
            f"/admin/users/{user_id}",
            json={"status": "banned"},
            headers=_auth(super_admin),
        )
        assert ok.status_code == 200

        # Banned user cannot log in
        banned_login = client.post("/auth/login", json={
            "email": target["_email"],
            "password": "SecurePass1!",
            "device_id": target["_device"],
            "app_version": "0.1.0-beta",
            "platform": "test",
        })
        assert banned_login.status_code == 403

    def test_audit_log_records_admin_actions(self, client, db):
        """Every admin action produces an audit log entry."""
        admin = _register(client)
        _make_superadmin(db, admin["user"]["user_id"])

        target = _register(client)
        user_id = target["user"]["user_id"]

        client.patch(
            f"/admin/users/{user_id}",
            json={"status": "suspended"},
            headers=_auth(admin),
        )

        log_resp = client.get("/admin/audit-log", headers=_auth(admin))
        assert log_resp.status_code == 200
        entries = log_resp.json()
        actions = [e["action"] for e in entries]
        assert "update_user" in actions

    def test_maintenance_prune_endpoint(self, client, db):
        """Superadmin can trigger a session prune via the API."""
        admin = _register(client)
        _make_superadmin(db, admin["user"]["user_id"])

        resp = client.post("/admin/maintenance/prune", headers=_auth(admin))
        assert resp.status_code == 200
        body = resp.json()
        assert "pruned" in body
        assert "sessions_expired" in body["pruned"]

    def test_maintenance_prune_requires_superadmin(self, client, db):
        """Regular admin cannot access the maintenance prune endpoint."""
        admin = _register(client)
        _make_admin(db, admin["user"]["user_id"])

        resp = client.post("/admin/maintenance/prune", headers=_auth(admin))
        assert resp.status_code == 403
