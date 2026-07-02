"""Atlas Accounts Service — feedback submission with server-side redaction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user_optional
from ..beta_acquisition import record_acquisition_event, sentiment_from_nps
from ..models import Feedback, User
from ..redaction import redact_feedback_message
from ..schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackCreate,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Store feedback with secrets and paths stripped before persistence."""
    contact = str(body.contact_email).strip() if body.contact_email else None
    redacted = redact_feedback_message(body.message, contact_email=contact)
    entry = Feedback(
        user_id=user.user_id if user else None,
        category=(body.category or "general")[:64],
        message_redacted=redacted,
        workflow=(body.workflow or None)[:64] if body.workflow else None,
        useful=body.useful,
        nps_score=body.nps_score,
        sentiment=sentiment_from_nps(body.nps_score),
    )
    db.add(entry)
    db.flush()
    if body.nps_score is not None and user:
        record_acquisition_event(
            db,
            "nps_submitted",
            user_id=user.user_id,
            metadata={"nps_score": body.nps_score, "category": entry.category},
            dedupe_user=False,
        )
    db.commit()
    db.refresh(entry)
    return entry
