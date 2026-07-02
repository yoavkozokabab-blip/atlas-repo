"""Phase 198 - billing license sync mapping."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_accounts_198.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "test-secret-do-not-use-in-prod-198")

from accounts_service.billing_sync import apply_remote_license
from accounts_service.database import Base, SessionLocal, engine
from accounts_service.models import License, User


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _user(db):
    user = User(email="phase198@example.com", password_hash="hash", status="active")
    db.add(user)
    db.flush()
    db.add(License(user_id=user.user_id, plan="free", status="active", max_devices=1))
    db.commit()
    db.refresh(user)
    return user


def test_phase198_remote_trial_maps_to_pro_trial_license(db):
    user = _user(db)
    trial_end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    lic = apply_remote_license(user, {
        "email": user.email,
        "plan": "trial",
        "status": "trial",
        "valid": True,
        "valid_until": trial_end,
        "trial_end": trial_end,
        "max_devices": 3,
    }, db)

    assert lic.plan == "pro"
    assert lic.status == "trial"
    assert lic.max_devices == 3
    assert lic.expires_at is not None


def test_phase198_remote_past_due_blocks_license(db):
    user = _user(db)

    lic = apply_remote_license(user, {
        "email": user.email,
        "plan": "pro",
        "status": "past_due",
        "valid": False,
        "valid_until": None,
        "max_devices": 3,
    }, db)

    assert lic.plan == "pro"
    assert lic.status == "past_due"
    assert lic.max_devices == 3

