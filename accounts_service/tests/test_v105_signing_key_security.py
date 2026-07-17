"""v1.0.5 per-installation signing key + migration security matrix.

No real or legacy secret values are ever printed by these tests.
"""
from __future__ import annotations

import importlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from accounts_service.signing_key_store import LocalSigningKeyStore, KEY_FILE_NAME


# ── key store unit behavior ────────────────────────────────────────────────
def test_create_and_load_roundtrip(tmp_path):
    store = LocalSigningKeyStore(tmp_path / "auth")
    assert store.load() is None
    key = store.create()
    assert len(key) >= 32
    assert store.load() == key
    assert (tmp_path / "auth" / KEY_FILE_NAME).is_file()


def test_key_file_is_not_plaintext_on_windows(tmp_path):
    store = LocalSigningKeyStore(tmp_path / "auth")
    key = store.create()
    raw = (tmp_path / "auth" / KEY_FILE_NAME).read_bytes()
    assert raw.startswith(b"ATLAS-SK1\x00")
    if sys.platform == "win32":
        # DPAPI-wrapped: raw key bytes must not appear in the file.
        assert raw[10:11] == b"D"
        assert key not in raw


def test_reuse_after_restart_same_key(tmp_path):
    d = tmp_path / "auth"
    first = LocalSigningKeyStore(d).load_or_create()
    second = LocalSigningKeyStore(d).load_or_create()  # simulated restart
    assert first == second


def test_two_installations_produce_different_keys(tmp_path):
    a = LocalSigningKeyStore(tmp_path / "A")
    b = LocalSigningKeyStore(tmp_path / "B")
    assert a.create() != b.create()
    assert a.fingerprint() != b.fingerprint()


def test_rotate_changes_key_and_fingerprint(tmp_path):
    store = LocalSigningKeyStore(tmp_path / "auth")
    k1, f1 = store.create(), store.fingerprint()
    k2, f2 = store.rotate(), store.fingerprint()
    assert k1 != k2 and f1 != f2


def test_fingerprint_is_nonsecret_and_short(tmp_path):
    store = LocalSigningKeyStore(tmp_path / "auth")
    key = store.create()
    fp = store.fingerprint()
    assert fp and len(fp) == 16
    assert fp.encode() not in key and key not in fp.encode()


# ── module reload helper: simulates one installation's service process ────
def _fresh_security(monkeypatch, data_dir: Path, env_secret: str | None = None):
    monkeypatch.delenv("ATLAS_AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("ATLAS_JWT_SECRET", raising=False)
    if env_secret is not None:
        monkeypatch.setenv("ATLAS_AUTH_JWT_SECRET", env_secret)
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(data_dir))
    import accounts_service.jwt_secret as jwt_secret
    import accounts_service.config as config
    import accounts_service.security as security

    importlib.reload(jwt_secret)
    importlib.reload(config)
    return importlib.reload(security)


def _issue(security, **overrides):
    return security.create_access_token(
        user_id=overrides.get("user_id", "u-1"),
        email=overrides.get("email", "user@example.com"),
        role=overrides.get("role", "user"),
        beta_flag=False,
        plan=overrides.get("plan", "free"),
    )


# ── token validation hardening ─────────────────────────────────────────────
def test_new_token_roundtrip_with_store_key_no_env(monkeypatch, tmp_path):
    security = _fresh_security(monkeypatch, tmp_path / "inst")
    token = _issue(security)
    payload = security.decode_access_token(token)
    assert payload["sub"] == "u-1"
    assert payload["jti"] and payload["kfp"]


def test_legacy_v104_access_token_rejected(monkeypatch, tmp_path):
    """A token signed with the exposed v1.0.4 fixed secret must fail."""
    import jwt as pyjwt

    security = _fresh_security(monkeypatch, tmp_path / "inst")
    now = datetime.now(timezone.utc)
    legacy = pyjwt.encode(
        {
            "sub": "u-legacy", "email": "user@example.com", "role": "user",
            "beta": False, "plan": "free", "iat": now,
            "exp": now + timedelta(minutes=15),
            "aud": "atlas-api", "iss": "atlas-auth",
        },
        "synthetic-legacy-v104-secret-for-tests-only!",  # stands in for the leaked value
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.PyJWTError):
        security.decode_access_token(legacy)


def test_token_without_active_key_fingerprint_rejected(monkeypatch, tmp_path):
    """Even a token signed with the *current* secret fails without the active
    kfp claim — covers upgrades where an operator pins the same env secret."""
    import jwt as pyjwt

    secret = "pinned-environment-secret-at-least-32-chars!"
    security = _fresh_security(monkeypatch, tmp_path / "inst", env_secret=secret)
    now = datetime.now(timezone.utc)
    no_kfp = pyjwt.encode(
        {
            "sub": "u-1", "email": "user@example.com", "role": "user",
            "beta": False, "plan": "free", "iat": now,
            "exp": now + timedelta(minutes=15),
            "aud": "atlas-api", "iss": "atlas-auth",
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.PyJWTError):
        security.decode_access_token(no_kfp)


def test_cross_installation_token_rejected(monkeypatch, tmp_path):
    security_a = _fresh_security(monkeypatch, tmp_path / "A")
    token_a = _issue(security_a)
    security_b = _fresh_security(monkeypatch, tmp_path / "B")
    import jwt as pyjwt

    with pytest.raises(pyjwt.PyJWTError):
        security_b.decode_access_token(token_a)
    # ...and B's own tokens work.
    assert security_b.decode_access_token(_issue(security_b))["sub"] == "u-1"


def test_malformed_expired_and_wrong_alg_rejected(monkeypatch, tmp_path):
    import jwt as pyjwt

    security = _fresh_security(monkeypatch, tmp_path / "inst")
    with pytest.raises(pyjwt.PyJWTError):
        security.decode_access_token("not.a.token")
    # expired
    now = datetime.now(timezone.utc)
    expired = pyjwt.encode(
        {"sub": "u", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1),
         "aud": "atlas-api", "iss": "atlas-auth", "kfp": "x"},
        security.JWT_SECRET, algorithm="HS256",
    )
    with pytest.raises(pyjwt.PyJWTError):
        security.decode_access_token(expired)
    # alg=none
    none_tok = pyjwt.encode(
        {"sub": "u", "aud": "atlas-api", "iss": "atlas-auth"}, key=None, algorithm="none"
    )
    with pytest.raises(pyjwt.PyJWTError):
        security.decode_access_token(none_tok)
    # wrong issuer/audience
    for bad in ({"iss": "evil"}, {"aud": "evil"}):
        claims = {
            "sub": "u", "iat": now, "exp": now + timedelta(minutes=5),
            "aud": "atlas-api", "iss": "atlas-auth", "kfp": "x",
        }
        claims.update(bad)
        tok = pyjwt.encode(claims, security.JWT_SECRET, algorithm="HS256")
        with pytest.raises(pyjwt.PyJWTError):
            security.decode_access_token(tok)


def test_missing_iat_or_exp_rejected(monkeypatch, tmp_path):
    import jwt as pyjwt

    security = _fresh_security(monkeypatch, tmp_path / "inst")
    now = datetime.now(timezone.utc)
    base = {"sub": "u", "aud": "atlas-api", "iss": "atlas-auth", "kfp": "x"}
    for omit_ok in ({"exp": now + timedelta(minutes=5)}, {"iat": now}):
        claims = dict(base)
        claims.update(omit_ok)  # each variant omits the *other* required claim
        tok = pyjwt.encode(claims, security.JWT_SECRET, algorithm="HS256")
        with pytest.raises(pyjwt.PyJWTError):
            security.decode_access_token(tok)


# ── migration behavior on a real sqlite database ───────────────────────────
def _make_db(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from accounts_service.models import Base, User, Session as DbSession

    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path/'accounts.db'}")
    Base.metadata.create_all(bind=engine)
    Maker = sessionmaker(bind=engine)
    db = Maker()
    user = User(user_id=str(uuid.uuid4()), email="keep-me@example.com",
                password_hash="x", status="active")
    db.add(user)
    for i in range(3):
        db.add(DbSession(
            session_id=str(uuid.uuid4()), user_id=user.user_id, device_id=f"dev-{i}",
            refresh_hash=f"legacyhash-{i:02d}" + "0" * 50,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=20),
        ))
    db.commit()
    return db, user


def test_migration_revokes_legacy_sessions_and_preserves_users(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path / "inst"))
    from accounts_service.key_migration import run_key_migration, migration_completed
    from accounts_service.models import Session as DbSession, User

    db, user = _make_db(tmp_path)
    assert not migration_completed(db)
    assert run_key_migration(db) is True
    # all legacy refresh sessions revoked with the migration reason
    live = db.query(DbSession).filter(DbSession.revoked_at == None).count()  # noqa: E711
    assert live == 0
    assert all(s.revoked_reason == "jwt_key_migration_v105"
               for s in db.query(DbSession).all())
    # marker recorded, users/account data intact
    assert migration_completed(db)
    assert db.query(User).filter_by(email="keep-me@example.com").count() == 1


def test_migration_runs_only_once_and_spares_new_sessions(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path / "inst"))
    from accounts_service.key_migration import run_key_migration
    from accounts_service.models import Session as DbSession

    db, user = _make_db(tmp_path)
    assert run_key_migration(db) is True
    # a post-migration session (i.e., a fresh login) must survive re-runs
    db.add(DbSession(
        session_id=str(uuid.uuid4()), user_id=user.user_id, device_id="dev-new",
        refresh_hash="newhash" + "0" * 57,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=20),
    ))
    db.commit()
    assert run_key_migration(db) is False  # idempotent
    live = db.query(DbSession).filter(DbSession.revoked_at == None).count()  # noqa: E711
    assert live == 1


def test_interrupted_migration_resumes_safely(monkeypatch, tmp_path):
    """A crash before the marker commit leaves no marker; rerun completes."""
    monkeypatch.setenv("ATLAS_ACCOUNTS_DATA_DIR", str(tmp_path / "inst"))
    from accounts_service.key_migration import run_key_migration, migration_completed
    from accounts_service.models import Session as DbSession
    from sqlalchemy import text

    db, _ = _make_db(tmp_path)
    # Simulate the interrupted first attempt: revocation happened but the
    # process died before the marker row was committed.
    db.execute(text("UPDATE sessions SET revoked_at = :n, revoked_reason = 'jwt_key_migration_v105'"),
               {"n": datetime.now(timezone.utc).replace(tzinfo=None)})
    db.commit()
    assert not migration_completed(db)
    assert run_key_migration(db) is True  # resumes and records the marker
    assert migration_completed(db)
    assert db.query(DbSession).filter(DbSession.revoked_at == None).count() == 0  # noqa: E711


def test_copying_database_alone_does_not_transfer_trust(monkeypatch, tmp_path):
    """Tokens minted on install A are useless against install B even if B
    receives a byte-for-byte copy of A's SQLite database."""
    import shutil
    import jwt as pyjwt

    security_a = _fresh_security(monkeypatch, tmp_path / "A")
    token_a = _issue(security_a)
    db_a, _ = _make_db(tmp_path / "dbA")
    db_a.close()
    (tmp_path / "dbB").mkdir()
    shutil.copy2(tmp_path / "dbA" / "accounts.db", tmp_path / "dbB" / "accounts.db")
    security_b = _fresh_security(monkeypatch, tmp_path / "B")  # key lives outside the DB
    with pytest.raises(pyjwt.PyJWTError):
        security_b.decode_access_token(token_a)
