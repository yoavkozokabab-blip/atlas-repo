"""Phase 199 — private beta acquisition metrics and funnel helpers."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import AcquisitionEvent, Feedback, InviteCode, UsageDaily, User

BETA_USER_TARGET = 25

FUNNEL_STAGES = (
    "landing_visit",
    "waitlist_signup",
    "app_installed",
    "registered",
    "approved",
    "first_scan",
    "weekly_active",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def sentiment_from_nps(nps: Optional[int]) -> Optional[str]:
    if nps is None:
        return None
    if nps >= 9:
        return "positive"
    if nps >= 7:
        return "neutral"
    return "negative"


def record_acquisition_event(
    db: Session,
    stage: str,
    *,
    user_id: Optional[str] = None,
    device_id: Optional[str] = None,
    source: str = "desktop",
    metadata: Optional[dict] = None,
    dedupe_user: bool = False,
) -> AcquisitionEvent:
    """Persist one funnel stage event. Optionally skip duplicate user+stage rows."""
    stage = (stage or "").strip()[:64]
    if dedupe_user and user_id:
        existing = (
            db.query(AcquisitionEvent)
            .filter(AcquisitionEvent.user_id == user_id, AcquisitionEvent.stage == stage)
            .first()
        )
        if existing:
            return existing
    row = AcquisitionEvent(
        user_id=user_id,
        device_id=device_id,
        stage=stage,
        source=(source or "desktop")[:64],
        metadata_=metadata or {},
    )
    db.add(row)
    return row


def _stage_counts(db: Session) -> Dict[str, int]:
    rows = (
        db.query(AcquisitionEvent.stage, func.count(AcquisitionEvent.event_id))
        .group_by(AcquisitionEvent.stage)
        .all()
    )
    return {stage: int(count) for stage, count in rows}


def _funnel_conversion(counts: Dict[str, int]) -> Dict[str, Optional[float]]:
    """Return stage-to-stage conversion rates (0–1) where denominators exist."""
    out: Dict[str, Optional[float]] = {}
    pairs = [
        ("landing_visit", "waitlist_signup"),
        ("waitlist_signup", "app_installed"),
        ("app_installed", "registered"),
        ("registered", "approved"),
        ("approved", "first_scan"),
        ("first_scan", "weekly_active"),
    ]
    for src, dst in pairs:
        denom = counts.get(src, 0)
        num = counts.get(dst, 0)
        out[f"{src}_to_{dst}"] = round(num / denom, 3) if denom else None
    return out


def _weekly_retention(db: Session, today: Optional[date] = None) -> Dict[str, Any]:
    """Users active in prior ISO week who also had usage in current ISO week."""
    today = today or _utcnow().date()
    cur_start = _week_start(today)
    prev_start = cur_start - timedelta(days=7)
    prev_end = cur_start - timedelta(days=1)
    cur_end = today

    def _active_user_ids(start: date, end: date) -> set[str]:
        rows = (
            db.query(UsageDaily.user_id)
            .filter(UsageDaily.date >= start, UsageDaily.date <= end)
            .filter(
                (UsageDaily.launches > 0)
                | (UsageDaily.scans > 0)
                | (UsageDaily.change_plans > 0)
                | (UsageDaily.debug_runs > 0)
                | (UsageDaily.what_breaks_runs > 0)
            )
            .distinct()
            .all()
        )
        return {r[0] for r in rows if r[0]}

    prev = _active_user_ids(prev_start, prev_end)
    cur = _active_user_ids(cur_start, cur_end)
    retained = prev & cur
    rate = round(len(retained) / len(prev), 3) if prev else None
    return {
        "prior_week_active": len(prev),
        "current_week_active": len(cur),
        "retained_users": len(retained),
        "weekly_retention_rate": rate,
        "week_start": cur_start.isoformat(),
    }


def _nps_metrics(db: Session) -> Dict[str, Any]:
    rows = (
        db.query(Feedback.nps_score)
        .filter(Feedback.nps_score.isnot(None))
        .all()
    )
    scores = [int(r[0]) for r in rows if r[0] is not None]
    if not scores:
        return {"nps_score": None, "nps_responses": 0, "promoters": 0, "passives": 0, "detractors": 0}
    promoters = sum(1 for s in scores if s >= 9)
    passives = sum(1 for s in scores if 7 <= s <= 8)
    detractors = sum(1 for s in scores if s <= 6)
    total = len(scores)
    nps = round(((promoters - detractors) / total) * 100)
    return {
        "nps_score": nps,
        "nps_responses": total,
        "promoters": promoters,
        "passives": passives,
        "detractors": detractors,
    }


def _feedback_rankings(db: Session, *, limit: int = 8) -> Dict[str, List[Dict[str, Any]]]:
    """Top feature requests and complaints from categorized feedback."""
    feature_rows = (
        db.query(Feedback.message_redacted, func.count(Feedback.feedback_id))
        .filter(Feedback.category == "missing_feature", Feedback.status.in_(("pending", "reviewed")))
        .group_by(Feedback.message_redacted)
        .order_by(func.count(Feedback.feedback_id).desc())
        .limit(limit)
        .all()
    )
    complaint_cats = ("bug", "confusing_ui")
    complaint_rows = (
        db.query(Feedback.category, Feedback.message_redacted, func.count(Feedback.feedback_id))
        .filter(Feedback.category.in_(complaint_cats), Feedback.status.in_(("pending", "reviewed")))
        .group_by(Feedback.category, Feedback.message_redacted)
        .order_by(func.count(Feedback.feedback_id).desc())
        .limit(limit)
        .all()
    )
    return {
        "top_feature_requests": [
            {"message": msg[:200], "count": int(cnt)} for msg, cnt in feature_rows
        ],
        "top_complaints": [
            {"category": cat, "message": msg[:200], "count": int(cnt)}
            for cat, msg, cnt in complaint_rows
        ],
    }


def _launch_verdict(
    *,
    active_beta: int,
    weekly_retention: Optional[float],
    nps: Optional[int],
    critical_bugs: int,
    beta_target: int = BETA_USER_TARGET,
) -> Dict[str, Any]:
    """Single headline answer: do users want Atlas before paid launch?"""
    signals: List[str] = []
    if active_beta >= beta_target:
        signals.append("beta_target_met")
    if weekly_retention is not None and weekly_retention >= 0.4:
        signals.append("retention_ok")
    if nps is not None and nps >= 30:
        signals.append("nps_ok")
    if critical_bugs <= 2:
        signals.append("bugs_low")

    if len(signals) >= 3 and (nps is None or nps >= 20):
        verdict = "strong_signal"
        headline = "Strong early signal — users are engaging and feedback is mostly positive."
    elif len(signals) >= 2:
        verdict = "mixed_signal"
        headline = "Mixed signal — keep interviewing beta users before a paid launch."
    else:
        verdict = "weak_signal"
        headline = "Weak signal — more beta users and feedback needed before launch."

    return {
        "verdict": verdict,
        "headline": headline,
        "signals_met": signals,
        "beta_target": beta_target,
        "beta_target_progress": round(min(active_beta / beta_target, 1.0), 2) if beta_target else 0,
    }


def _normalize_invite(code: str) -> str:
    return (code or "").strip().upper().replace("-", "")


def redeem_invite_code(db: Session, code: str, email: str) -> "InviteCode":
    """Validate and consume one use of an invite code. Raises ValueError on failure."""
    from .models import InviteCode

    normalized = _normalize_invite(code)
    invite = db.query(InviteCode).filter(InviteCode.code == normalized).first()
    if not invite:
        raise ValueError("Invalid invite code.")
    if invite.status != "active":
        raise ValueError(f"Invite code is {invite.status}.")
    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        invite.status = "expired"
        raise ValueError("Invite code has expired.")
    if invite.use_count >= invite.max_uses:
        raise ValueError("Invite code has already been used.")
    if invite.email and invite.email.lower() != email.lower():
        raise ValueError("This invite code is reserved for a different email address.")
    invite.use_count += 1
    if invite.use_count >= invite.max_uses:
        invite.status = "expired"
    return invite


def compute_launch_readiness(db: Session) -> Dict[str, Any]:
    """Aggregate all Phase 199 launch-readiness KPIs for the admin dashboard."""
    counts = _stage_counts(db)
    nps = _nps_metrics(db)
    retention = _weekly_retention(db)

    active_beta = (
        db.query(func.count(User.user_id))
        .filter(User.beta_flag == True, User.status.in_(("beta", "active")))  # noqa: E712
        .scalar()
        or 0
    )
    waitlist = counts.get("waitlist_signup", 0)
    critical_bugs = (
        db.query(func.count(Feedback.feedback_id))
        .filter(Feedback.category == "bug", Feedback.status == "pending")
        .scalar()
        or 0
    )
    open_features = (
        db.query(func.count(Feedback.feedback_id))
        .filter(Feedback.category == "missing_feature", Feedback.status.in_(("pending", "reviewed")))
        .scalar()
        or 0
    )
    feedback_pending = (
        db.query(func.count(Feedback.feedback_id))
        .filter(Feedback.status == "pending")
        .scalar()
        or 0
    )
    sentiment_counts = Counter(
        s for (s,) in db.query(Feedback.sentiment).filter(Feedback.sentiment.isnot(None)).all() if s
    )
    rankings = _feedback_rankings(db)

    verdict = _launch_verdict(
        active_beta=int(active_beta),
        weekly_retention=retention.get("weekly_retention_rate"),
        nps=nps.get("nps_score"),
        critical_bugs=int(critical_bugs),
    )

    return {
        "waitlist_count": waitlist,
        "active_beta_users": int(active_beta),
        "weekly_retention": retention,
        "nps": nps,
        "sentiment": dict(sentiment_counts),
        "critical_bugs": int(critical_bugs),
        "open_feature_requests": int(open_features),
        "feedback_pending": int(feedback_pending),
        "funnel_counts": {stage: counts.get(stage, 0) for stage in FUNNEL_STAGES},
        "funnel_conversion": _funnel_conversion(counts),
        "top_feature_requests": rankings["top_feature_requests"],
        "top_complaints": rankings["top_complaints"],
        "launch_verdict": verdict,
        "invite_codes_active": (
            db.query(func.count(InviteCode.invite_id))
            .filter(InviteCode.status == "active")
            .scalar()
            or 0
        ),
    }


def export_beta_users(db: Session, *, limit: int = 500) -> List[Dict[str, Any]]:
    """Export beta users for interview scheduling."""
    users = (
        db.query(User)
        .filter(User.beta_flag == True)  # noqa: E712
        .order_by(User.created_at.desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for u in users:
        profile = u.beta_profile
        out.append({
            "user_id": u.user_id,
            "email": u.email,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
            "primary_role": profile.primary_role if profile else None,
            "company_name": profile.company_name if profile else None,
            "atlas_help": profile.atlas_help if profile else [],
        })
    return out


def feedback_summary(db: Session) -> Dict[str, Any]:
    """Structured feedback summary for user interviews."""
    by_category = (
        db.query(Feedback.category, func.count(Feedback.feedback_id))
        .group_by(Feedback.category)
        .all()
    )
    by_status = (
        db.query(Feedback.status, func.count(Feedback.feedback_id))
        .group_by(Feedback.status)
        .all()
    )
    return {
        "by_category": {cat: int(n) for cat, n in by_category},
        "by_status": {st: int(n) for st, n in by_status},
        "nps": _nps_metrics(db),
        "rankings": _feedback_rankings(db, limit=10),
    }
