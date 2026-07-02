"""Atlas Accounts Service — authenticated user endpoints."""
from __future__ import annotations

import sys, os
_lib = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from datetime import datetime, date, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..billing_sync import BillingSyncError, sync_billing_license
from ..models import Device, License, User, UsageDaily
from ..schemas import DeviceOut, LicenseCheckResponse, LicenseOut, UserOut

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/license", response_model=LicenseCheckResponse)
def license_check(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Desktop client polls this to validate license + get feature flags."""
    # Non-punitive, not-yet-active account states resolve to an invalid license
    # so the desktop app routes the user to an in-app status dashboard rather
    # than the product (Phase 193). The user.status drives the dashboard shown.
    _INACTIVE_STATUS_MESSAGES = {
        "pending": "Your account was created and is waiting for beta approval.",
        "inactive": "Your Atlas account is not active right now.",
        "expired": "Your Atlas access has expired.",
        "rejected": "Your beta application was not approved.",
    }
    if user.status in _INACTIVE_STATUS_MESSAGES:
        lic = user.license
        return LicenseCheckResponse(
            valid=False,
            plan=lic.plan if lic else "free",
            status=user.status,
            expires_at=lic.expires_at if lic else None,
            max_devices=lic.max_devices if lic else 1,
            beta_features=False,
            message=_INACTIVE_STATUS_MESSAGES[user.status],
        )
    try:
        synced = sync_billing_license(user, db)
        if synced is not None:
            db.refresh(user)
    except BillingSyncError as exc:
        return LicenseCheckResponse(
            valid=False,
            plan="free",
            status="billing_sync_failed",
            max_devices=1,
            beta_features=False,
            message=str(exc),
        )

    lic = user.license
    if not lic:
        return LicenseCheckResponse(
            valid=False,
            plan="free",
            status="none",
            max_devices=1,
            beta_features=False,
            message="No active license. Contact support.",
        )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if lic.expires_at and lic.expires_at < now:
        return LicenseCheckResponse(
            valid=False,
            plan=lic.plan,
            status="expired",
            expires_at=lic.expires_at,
            max_devices=lic.max_devices,
            beta_features=False,
            message="License expired. Contact support@useatlas.dev.",
        )
    _INACTIVE_LICENSE_MESSAGES = {
        "expired": "License expired. Contact support@useatlas.dev.",
        "past_due": "Payment is past due. Update billing to continue using Atlas.",
        "canceled": "Subscription canceled. Reactivate billing to continue using Atlas.",
        "cancelled": "Subscription cancelled. Reactivate billing to continue using Atlas.",
        "suspended": "License suspended. Contact support@useatlas.dev.",
    }
    if lic.status in _INACTIVE_LICENSE_MESSAGES:
        return LicenseCheckResponse(
            valid=False,
            plan=lic.plan,
            status=lic.status,
            expires_at=lic.expires_at,
            max_devices=lic.max_devices,
            beta_features=False,
            message=_INACTIVE_LICENSE_MESSAGES[lic.status],
        )
    if lic.status == "trial" and not lic.expires_at:
        return LicenseCheckResponse(
            valid=False,
            plan=lic.plan,
            status="trial_missing_expiry",
            expires_at=lic.expires_at,
            max_devices=lic.max_devices,
            beta_features=False,
            message="Trial license is missing an expiry date. Contact support@useatlas.dev.",
        )
    if lic.status not in {"active", "trial"}:
        return LicenseCheckResponse(
            valid=False,
            plan=lic.plan,
            status=lic.status,
            expires_at=lic.expires_at,
            max_devices=lic.max_devices,
            beta_features=False,
            message="No active license. Contact support.",
        )
    return LicenseCheckResponse(
        valid=True,
        plan=lic.plan,
        status=lic.status,
        expires_at=lic.expires_at,
        max_devices=lic.max_devices,
        beta_features=user.beta_flag or lic.plan in {"beta", "pro", "enterprise"},
    )


@router.get("/devices", response_model=List[DeviceOut])
def list_devices(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Device).filter(Device.user_id == user.user_id).all()


@router.delete("/devices/{device_id}", status_code=204)
def remove_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User self-service: revoke one of their own devices."""
    device = db.query(Device).filter(
        Device.device_id == device_id,
        Device.user_id == user.user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")
    device.status = "revoked"
    from ..models import Session as DBSession
    from datetime import datetime, timezone
    db.query(DBSession).filter(
        DBSession.device_id == device_id,
        DBSession.revoked_at == None,  # noqa: E711
    ).update({"revoked_at": datetime.now(timezone.utc).replace(tzinfo=None), "revoked_reason": "user_removed"})
    db.commit()
