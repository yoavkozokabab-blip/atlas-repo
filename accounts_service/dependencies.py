"""Atlas Accounts Service — FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import sys, os
_lib = os.path.join(os.path.dirname(__file__), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import Device, Session as DBSession, User
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Optional variant: does not raise 401 if no token
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _get_user_from_token(token: str, db: Session) -> User:
    """Decode JWT, load User from DB. Raises HTTPException on any failure."""
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    session_id: Optional[str] = payload.get("session_id")
    device_id: Optional[str] = payload.get("device_id")
    if not session_id or not device_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = (
        db.query(DBSession)
        .filter(DBSession.session_id == session_id, DBSession.user_id == user_id)
        .first()
    )
    if (
        not session
        or session.device_id != device_id
        or session.revoked_at is not None
        or session.expires_at <= now
    ):
        raise HTTPException(status_code=401, detail="Session is no longer valid")

    device = (
        db.query(Device)
        .filter(Device.device_id == device_id, Device.user_id == user_id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=401, detail="Device not found")
    if device.status == "revoked":
        raise HTTPException(status_code=403, detail="Device has been revoked")
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Require a valid JWT and return the authenticated User."""
    user = _get_user_from_token(token, db)
    if user.status in ("suspended", "banned", "expired"):
        raise HTTPException(
            status_code=403,
            detail=f"Account {user.status}. Contact support@useatlas.dev.",
        )
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated User if a valid token is present, else None."""
    if not token:
        return None
    try:
        return _get_user_from_token(token, db)
    except HTTPException:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin or superadmin role."""
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    """Require superadmin role (for role changes, banning)."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return user
