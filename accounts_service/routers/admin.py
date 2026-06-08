"""Atlas Accounts Service — admin endpoints. All actions write to AdminAuditLog."""
from __future__ import annotations

import sys, os
_lib = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_admin, require_superadmin
from ..models import (
    AdminAuditLog, AdminNotification, Device, Feedback, License,
    Session as DBSession, User, UsageDaily,
)
from ..schemas import (
    AdminAuditEntry, AdminDashboard, AdminNotificationOut, AdminUserOut, AdminUserUpdate,
    ApplicationDecisionRequest, FeedbackOut, PendingApplicationOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(
    db: Session,
    admin: User,
    action: str,
    target_user: Optional[User] = None,
    target_device_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Write an immutable audit log entry."""
    entry = AdminAuditLog(
        admin_user_id=admin.user_id,
        admin_email=admin.email,
        action=action,
        target_user_id=target_user.user_id if target_user else None,
        target_user_email=target_user.email if target_user else None,
        target_device_id=target_device_id,
        metadata_=metadata or {},
    )
    db.add(entry)


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ── Dashboard ──────────────────────────────────────────────────────────────
@router.get("/dashboard", response_model=AdminDashboard)
def dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = _today()

    total = db.query(func.count(User.user_id)).scalar() or 0
    active = db.query(func.count(User.user_id)).filter(User.status.in_(("active", "beta"))).scalar() or 0
    beta = db.query(func.count(User.user_id)).filter(User.beta_flag == True).scalar() or 0  # noqa: E712
    suspended = db.query(func.count(User.user_id)).filter(User.status == "suspended").scalar() or 0
    banned = db.query(func.count(User.user_id)).filter(User.status == "banned").scalar() or 0
    active_devices = db.query(func.count(Device.device_id)).filter(Device.status == "active").scalar() or 0

    today_usage = (
        db.query(
            func.coalesce(func.sum(UsageDaily.launches), 0),
            func.coalesce(func.sum(UsageDaily.scans), 0),
            func.coalesce(func.sum(UsageDaily.exports), 0),
            func.coalesce(func.sum(UsageDaily.estimated_tokens_saved), 0),
        )
        .filter(UsageDaily.date == today)
        .first()
    ) or (0, 0, 0, 0)

    feedback_pending = (
        db.query(func.count(Feedback.feedback_id)).filter(Feedback.status == "pending").scalar() or 0
    )
    pending_applications = (
        db.query(func.count(User.user_id)).filter(User.status == "pending").scalar() or 0
    )
    unread_notifications = (
        db.query(func.count(AdminNotification.notification_id))
        .filter(AdminNotification.read_at == None)  # noqa: E711
        .scalar() or 0
    )

    return AdminDashboard(
        total_users=total,
        active_users=active,
        beta_users=beta,
        suspended_users=suspended,
        banned_users=banned,
        active_devices=active_devices,
        launches_today=today_usage[0],
        scans_today=today_usage[1],
        exports_today=today_usage[2],
        tokens_saved_today=today_usage[3],
        feedback_pending=feedback_pending,
        pending_applications=pending_applications,
        unread_notifications=unread_notifications,
    )


# ── User list ──────────────────────────────────────────────────────────────
@router.get("/users", response_model=List[AdminUserOut])
def list_users(
    q: Optional[str] = Query(None, description="Search by email"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if q:
        query = query.filter(User.email.ilike(f"%{q}%"))
    if status:
        query = query.filter(User.status == status)
    return query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/applications/pending", response_model=List[PendingApplicationOut])
def list_pending_applications(
    limit: int = Query(100, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Pending beta applications with full intake profile."""
    users = (
        db.query(User)
        .filter(User.status == "pending")
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        PendingApplicationOut(
            user_id=u.user_id,
            email=u.email,
            status=u.status,
            created_at=u.created_at,
            admin_notes=u.admin_notes,
            beta_profile=u.beta_profile,
        )
        for u in users
    ]


@router.get("/notifications", response_model=List[AdminNotificationOut])
def list_notifications(
    unread_only: bool = Query(True),
    limit: int = Query(20, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AdminNotification).order_by(AdminNotification.created_at.desc())
    if unread_only:
        query = query.filter(AdminNotification.read_at == None)  # noqa: E711
    return query.limit(limit).all()


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    note = db.query(AdminNotification).filter(
        AdminNotification.notification_id == notification_id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    note.read_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


@router.post("/users/{user_id}/approve-application", response_model=AdminUserOut)
def approve_application(
    user_id: str,
    body: ApplicationDecisionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.beta_flag = True
    user.status = "beta"
    if body.admin_notes:
        user.admin_notes = body.admin_notes
    lic = user.license
    if lic:
        lic.plan = "beta"
        lic.max_devices = 3
    db.query(AdminNotification).filter(
        AdminNotification.user_id == user_id,
        AdminNotification.read_at == None,  # noqa: E711
    ).update({"read_at": datetime.now(timezone.utc).replace(tzinfo=None)})
    _audit(db, admin, "approve_application", user, metadata={"notes": body.admin_notes})
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reject-application", response_model=AdminUserOut)
def reject_application(
    user_id: str,
    body: ApplicationDecisionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "rejected"
    user.beta_flag = False
    if body.admin_notes:
        user.admin_notes = body.admin_notes
    db.query(AdminNotification).filter(
        AdminNotification.user_id == user_id,
        AdminNotification.read_at == None,  # noqa: E711
    ).update({"read_at": datetime.now(timezone.utc).replace(tzinfo=None)})
    _audit(db, admin, "reject_application", user, metadata={"notes": body.admin_notes})
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=AdminUserOut)
def get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── User actions ───────────────────────────────────────────────────────────
@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update status, role, beta_flag, plan, device limit, or admin notes."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Require superadmin for banning, unbanning, or role changes
    if body.status == "banned" and admin.role != "superadmin":
        raise HTTPException(status_code=403, detail="Banning requires superadmin role.")
    if (
        body.status is not None
        and user.status == "banned"
        and body.status != "banned"
        and admin.role != "superadmin"
    ):
        raise HTTPException(status_code=403, detail="Unbanning requires superadmin role.")
    if body.role and admin.role != "superadmin":
        raise HTTPException(status_code=403, detail="Role changes require superadmin.")

    before = {"status": user.status, "role": user.role, "beta_flag": user.beta_flag}

    if body.status is not None:
        user.status = body.status
    if body.role is not None:
        user.role = body.role
    if body.beta_flag is not None:
        user.beta_flag = body.beta_flag
    if body.admin_notes is not None:
        user.admin_notes = body.admin_notes

    # License changes
    if body.plan is not None or body.max_devices is not None or body.expires_at is not None:
        lic = user.license
        if not lic:
            lic = License(user_id=user.user_id, plan="free", status="active", max_devices=1)
            db.add(lic)
        if body.plan is not None:
            lic.plan = body.plan
        if body.max_devices is not None:
            lic.max_devices = body.max_devices
        if body.expires_at is not None:
            lic.expires_at = body.expires_at

    after = {"status": user.status, "role": user.role, "beta_flag": user.beta_flag}

    _audit(db, admin, "update_user", user, metadata={"before": before, "after": after})
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/grant-beta", response_model=AdminUserOut)
def grant_beta(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.beta_flag = True
    user.status = "beta"
    lic = user.license
    if lic:
        lic.plan = "beta"
        lic.max_devices = 3
    _audit(db, admin, "grant_beta", user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/revoke-beta", response_model=AdminUserOut)
def revoke_beta(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.beta_flag = False
    if user.status == "beta":
        user.status = "active"
    lic = user.license
    if lic and lic.plan == "beta":
        lic.plan = "free"
        lic.max_devices = 1
    _audit(db, admin, "revoke_beta", user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/force-logout", status_code=204)
def force_logout(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke all active sessions for a user."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(DBSession).filter(
        DBSession.user_id == user_id,
        DBSession.revoked_at == None,  # noqa: E711
    ).update({"revoked_at": now, "revoked_reason": "force_logout"})
    _audit(db, admin, "force_logout", user)
    db.commit()


# ── Device management ──────────────────────────────────────────────────────
@router.delete("/users/{user_id}/devices/{device_id}", status_code=204)
def revoke_device(
    user_id: str,
    device_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    device = db.query(Device).filter(
        Device.device_id == device_id,
        Device.user_id == user_id,
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.status = "revoked"
    device.revoked_by = admin.user_id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(DBSession).filter(
        DBSession.device_id == device_id,
        DBSession.revoked_at == None,  # noqa: E711
    ).update({"revoked_at": now, "revoked_reason": "admin_revoked"})
    user = db.query(User).filter(User.user_id == user_id).first()
    _audit(db, admin, "revoke_device", user, target_device_id=device_id)
    db.commit()


# ── Audit log ──────────────────────────────────────────────────────────────
@router.get("/audit-log", response_model=List[AdminAuditEntry])
def audit_log(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ── Maintenance ────────────────────────────────────────────────────────────

@router.post("/maintenance/prune", status_code=200)
def maintenance_prune(
    admin: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Prune expired/old sessions and used email tokens.  Superadmin only.

    Returns pruning statistics so the operator can verify the operation.
    Safe to call at any time — only deletes rows that can never be used again.
    """
    from ..session_cleanup import prune_all
    stats = prune_all(db)
    _audit(db, admin, "maintenance_prune", metadata={"pruned": stats})
    # prune_all already committed; audit entry needs an explicit commit
    db.commit()
    return {"pruned": stats}


# ── Feedback inbox ─────────────────────────────────────────────────────────
@router.get("/feedback", response_model=List[FeedbackOut])
def list_feedback(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Feedback)
    if status:
        query = query.filter(Feedback.status == status)
    return query.order_by(Feedback.created_at.desc()).limit(limit).all()
