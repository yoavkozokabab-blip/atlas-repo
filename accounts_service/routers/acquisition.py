"""Phase 199 — acquisition funnel event ingestion (privacy-safe)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..beta_acquisition import record_acquisition_event
from ..beta_acquisition import _normalize_invite
from ..database import get_db
from ..dependencies import get_current_user_optional
from ..models import InviteCode, User
from ..schemas import AcquisitionEventCreate, InviteValidateRequest, InviteValidateResponse

router = APIRouter(prefix="/acquisition", tags=["acquisition"])


@router.post("/event", status_code=204)
def ingest_event(
    body: AcquisitionEventCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Record a funnel stage. Authenticated users attach user_id automatically."""
    device_id = (body.device_id or "")[:64] or None
    record_acquisition_event(
        db,
        body.stage,
        user_id=user.user_id if user else None,
        device_id=device_id,
        source=body.source,
        metadata=body.metadata,
        dedupe_user=bool(user),
    )
    db.commit()


@router.post("/validate-invite", response_model=InviteValidateResponse)
def validate_invite(body: InviteValidateRequest, db: Session = Depends(get_db)):
    """Check whether an invite code is valid before registration."""
    code = _normalize_invite(body.code)
    if not code:
        return InviteValidateResponse(valid=False, message="Enter an invite code.")

    invite = db.query(InviteCode).filter(InviteCode.code == code).first()
    if not invite:
        return InviteValidateResponse(valid=False, message="Invite code not found.")
    if invite.status != "active":
        return InviteValidateResponse(valid=False, message=f"Invite code is {invite.status}.")
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        invite.status = "expired"
        db.commit()
        return InviteValidateResponse(valid=False, message="Invite code has expired.")
    if invite.use_count >= invite.max_uses:
        return InviteValidateResponse(valid=False, message="Invite code has already been used.")

    hint = None
    if invite.email:
        parts = invite.email.split("@")
        if len(parts) == 2 and parts[0]:
            hint = f"{parts[0][:2]}***@{parts[1]}"
    return InviteValidateResponse(valid=True, email_hint=hint, message="Invite code accepted.")
