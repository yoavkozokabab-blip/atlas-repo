"""Atlas Accounts Service — auth routes (register, login, logout, refresh)."""
from __future__ import annotations

import sys, os
_lib = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..beta_acquisition import record_acquisition_event, redeem_invite_code
from ..database import get_db
from ..models import AdminNotification, BetaProfile, Device, EmailToken, License, Session as DBSession, User
from ..rate_limit import check_rate_limit
from ..schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from ..security import (
    _DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    refresh_token_expiry,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Punitive statuses that are refused at login (no token issued). Non-punitive
# inactive states (pending / inactive / expired / rejected) DO receive a token so
# the desktop app can route them to an in-app status dashboard instead of a
# dead-end access wall (Phase 193).
BLOCKED_STATUSES = ("suspended", "banned")


def _user_plan(user: User) -> str:
    return user.license.plan if user.license else "free"


def _build_token_response(user: User, device_id: str, db: Session) -> TokenResponse:
    """Create access + refresh tokens, persist session, return full response."""
    raw_refresh = generate_refresh_token()
    refresh_hash = hash_token(raw_refresh)

    db_session = DBSession(
        user_id=user.user_id,
        device_id=device_id,
        refresh_hash=refresh_hash,
        expires_at=refresh_token_expiry(),
    )
    db.add(db_session)
    db.flush()

    access_token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        beta_flag=user.beta_flag,
        plan=_user_plan(user),
        extra={"session_id": db_session.session_id, "device_id": device_id},
    )

    # Update last_seen
    user.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    from ..schemas import LicenseOut, UserOut
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user=UserOut.model_validate(user),
        license=LicenseOut.model_validate(user.license) if user.license else None,
    )


def _ensure_device(
    user: User,
    device_id: str,
    app_version: str,
    platform: str,
    db: Session,
) -> Device:
    """Register device if new; update last_seen if known."""
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if device:
        if device.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="Device ID is already registered to another account.")
        # Existing device — update heartbeat
        device.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
        device.app_version = app_version
        if device.status == "revoked":
            raise HTTPException(status_code=403, detail="Device has been revoked. Contact support.")
        return device

    # New device — check limit
    max_devices = user.license.max_devices if user.license else 1
    active_count = (
        db.query(Device)
        .filter(Device.user_id == user.user_id, Device.status == "active")
        .count()
    )
    if active_count >= max_devices:
        raise HTTPException(
            status_code=403,
            detail=f"Device limit reached ({active_count}/{max_devices}). "
                   "Remove a device from your account to add this one.",
        )

    device = Device(
        device_id=device_id,
        user_id=user.user_id,
        app_version=app_version,
        platform=platform,
    )
    db.add(device)
    return device


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Create a new account and immediately issue tokens (no email verify gate for beta)."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(f"register:{client_ip}", max_calls=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Too many registrations. Try again later.")

    # Normalise email
    email = req.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    if req.invite_code:
        try:
            redeem_invite_code(db, req.invite_code, email)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = User(
        email=email,
        password_hash=hash_password(req.password),
        status="pending",
        role="user",
        beta_flag=False,
    )
    db.add(user)
    db.flush()  # get user_id

    # Default license (free)
    lic = License(user_id=user.user_id, plan="free", status="active", max_devices=1)
    db.add(lic)
    db.flush()

    # Invite code = instant beta access (no manual admin approval for invited strangers).
    if req.invite_code:
        user.beta_flag = True
        user.status = "beta"
        lic.plan = "beta"
        lic.max_devices = 3
        record_acquisition_event(
            db,
            "approved",
            user_id=user.user_id,
            device_id=req.device_id[:64],
            metadata={"via": "invite_code"},
            dedupe_user=True,
        )

    if req.beta_profile:
        profile = BetaProfile(user_id=user.user_id, **req.beta_profile.model_dump())
        db.add(profile)
        db.flush()
        summary = {
            "primary_role": req.beta_profile.primary_role,
            "developer_experience": req.beta_profile.developer_experience,
            "currently_developer": req.beta_profile.currently_developer,
            "company_name": req.beta_profile.company_name,
            "company_size": req.beta_profile.company_size,
            "project_use": req.beta_profile.project_use,
            "repo_size": req.beta_profile.repo_size,
            "coding_tools": req.beta_profile.coding_tools,
            "languages_frameworks": req.beta_profile.languages_frameworks,
            "atlas_help": req.beta_profile.atlas_help,
        }
        db.add(AdminNotification(
            kind="beta_application",
            user_id=user.user_id,
            email=user.email,
            summary=summary,
        ))

    _ensure_device(user, req.device_id, req.app_version, req.platform, db)
    record_acquisition_event(
        db,
        "registered",
        user_id=user.user_id,
        device_id=req.device_id[:64],
        dedupe_user=True,
    )
    if req.invite_code:
        record_acquisition_event(
            db,
            "waitlist_signup",
            user_id=user.user_id,
            device_id=req.device_id[:64],
            metadata={"via": "invite_code"},
            dedupe_user=True,
        )
    return _build_token_response(user, req.device_id, db)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate and issue tokens. Never reveals whether email exists."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(f"login:{client_ip}", max_calls=5, window_seconds=900):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please wait 15 minutes.",
        )

    email = req.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Always verify even if user is not found to keep timing roughly consistent.
    candidate_hash = user.password_hash if user else _DUMMY_HASH
    valid = verify_password(req.password, candidate_hash)

    # Anti-enumeration (Phase 186D): return one identical response whether the
    # email is unknown or the password is wrong. The dummy-hash verify above keeps
    # timing roughly constant; this keeps the message constant too. Never reveal
    # which field failed.
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if user.status in BLOCKED_STATUSES:
        reason_map = {
            "suspended": "Your account has been suspended. Contact yoavkozokabab@gmail.com.",
            "banned": "Your account has been banned. Contact yoavkozokabab@gmail.com.",
            "expired": "Your access has expired. Contact yoavkozokabab@gmail.com.",
        }
        raise HTTPException(status_code=403, detail=reason_map.get(user.status, "Account not available."))

    _ensure_device(user, req.device_id, req.app_version, req.platform, db)
    return _build_token_response(user, req.device_id, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(req: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token (with rotation)."""
    refresh_hash = hash_token(req.refresh_token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = (
        db.query(DBSession)
        .filter(
            DBSession.refresh_hash == refresh_hash,
            DBSession.revoked_at == None,  # noqa: E711
            DBSession.expires_at > now,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    # Verify device match
    if session.device_id != req.device_id:
        # Possible token theft — revoke this session
        session.revoked_at = now
        session.revoked_reason = "device_mismatch"
        db.commit()
        raise HTTPException(status_code=401, detail="Device mismatch. Please log in again.")

    user = db.query(User).filter(User.user_id == session.user_id).first()
    if not user or user.status in BLOCKED_STATUSES:
        raise HTTPException(status_code=403, detail="Account not available.")

    # Rotate: revoke old session
    session.revoked_at = now
    session.revoked_reason = "rotation"

    return _build_token_response(user, req.device_id, db)


@router.post("/logout", status_code=204)
def logout(req: LogoutRequest, db: Session = Depends(get_db)):
    """Revoke a refresh token (logout from this device)."""
    refresh_hash = hash_token(req.refresh_token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = db.query(DBSession).filter(DBSession.refresh_hash == refresh_hash).first()
    if session and not session.revoked_at:
        session.revoked_at = now
        session.revoked_reason = "logout"
        db.commit()
    # Always 204 — no information leakage
