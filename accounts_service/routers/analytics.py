"""Atlas Accounts Service — usage analytics ingestion.

Privacy contract: this router accepts ONLY integer counters + metadata.
It will reject any payload containing string fields that could carry code,
repository paths, or prompt text. See PrivacyValidator below.
"""
from __future__ import annotations

import sys, os
_lib = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)

import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Device, UsageDaily, User
from ..schemas import UsageEventRequest

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Regex that catches common secret / path patterns — defence in depth
_SECRET_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|token|bearer|auth|sk-[a-z0-9]+|/[a-z]|[a-z]:\\)",
    re.IGNORECASE,
)


class PrivacyValidator:
    """Verify that no string field in the analytics payload carries sensitive data."""

    ALLOWED_STRING_FIELDS = {"event_type", "app_version", "date", "device_id"}

    @staticmethod
    def validate(payload: dict) -> None:
        """Raise ValueError if any string field looks like code, path, or secret."""
        for key, value in payload.items():
            if not isinstance(value, str):
                continue
            if key not in PrivacyValidator.ALLOWED_STRING_FIELDS:
                raise ValueError(f"Unexpected string field in analytics payload: {key!r}")
            if key == "event_type" and len(value) > 64:
                raise ValueError("event_type too long")
            if key == "app_version" and len(value) > 32:
                raise ValueError("app_version too long")
            if key == "device_id" and (len(value) > 64 or not re.fullmatch(r"[a-f0-9]+", value, re.I)):
                raise ValueError("device_id must be a short hex identifier")
            if _SECRET_PATTERN.search(value):
                raise ValueError(f"Field {key!r} appears to contain sensitive data")


ALLOWED_EVENT_TYPES = {
    "app_started",
    "scan_completed",
    "change_plan_generated",
    "debug_generated",
    "what_breaks_generated",
    "export_copied",
    "feedback_submitted",
    "heartbeat",
}


@router.post("/event", status_code=204)
def record_event(
    req: UsageEventRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest a usage event. Validates that no sensitive data is present."""
    # Validate privacy
    try:
        PrivacyValidator.validate(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if req.event_type not in ALLOWED_EVENT_TYPES:
        # Unknown event types are silently accepted but clamped to safe fields
        pass

    # Resolve date
    event_date: date
    if req.date:
        try:
            event_date = date.fromisoformat(req.date)
        except ValueError:
            event_date = datetime.now(timezone.utc).date()
    else:
        event_date = datetime.now(timezone.utc).date()

    # Upsert usage_daily (SQLite-friendly approach)
    existing = (
        db.query(UsageDaily)
        .filter(
            UsageDaily.user_id == user.user_id,
            UsageDaily.device_id == req.device_id,
            UsageDaily.date == event_date,
        )
        .first()
    )
    if existing:
        existing.launches += req.launches
        existing.scans += req.scans
        existing.change_plans += req.change_plans
        existing.debug_runs += req.debug_runs
        existing.what_breaks_runs += req.what_breaks_runs
        existing.exports += req.exports
        existing.estimated_tokens_saved += req.estimated_tokens_saved
    else:
        row = UsageDaily(
            user_id=user.user_id,
            device_id=req.device_id,
            date=event_date,
            launches=req.launches,
            scans=req.scans,
            change_plans=req.change_plans,
            debug_runs=req.debug_runs,
            what_breaks_runs=req.what_breaks_runs,
            exports=req.exports,
            estimated_tokens_saved=req.estimated_tokens_saved,
        )
        db.add(row)

    db.commit()
