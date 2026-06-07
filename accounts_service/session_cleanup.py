"""Atlas Accounts Service — session and token pruning.

Called at startup to remove expired/revoked rows that would otherwise
accumulate indefinitely.  Also exposed via the admin maintenance endpoint
so an operator can trigger an out-of-schedule prune.

Safety invariants:
  - Only deletes rows that can *never* be used again (expired or revoked).
  - Active sessions (revoked_at IS NULL and expires_at > now) are untouched.
  - Revoked-but-not-yet-expired sessions are kept for _REVOKED_RETENTION_DAYS
    for audit-trail purposes, then deleted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy.orm import Session as DBSession

from .models import EmailToken
from .models import Session as SessionModel

# Keep revoked sessions for 7 days even after revocation (audit trail).
_REVOKED_RETENTION_DAYS: int = 7


def prune_sessions(db: DBSession) -> Dict[str, int]:
    """Delete sessions that are no longer usable.

    Deletes:
      - Any session whose refresh token has expired (``expires_at <= now``).
      - Any session that was revoked ≥ _REVOKED_RETENTION_DAYS ago and is
        not already caught by the expiry clause.

    Does NOT commit — caller must commit.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    revoke_cutoff = now - timedelta(days=_REVOKED_RETENTION_DAYS)

    # 1. Expired sessions (can no longer be used for refresh regardless of revocation status)
    expired_deleted: int = (
        db.query(SessionModel)
        .filter(SessionModel.expires_at <= now)
        .delete(synchronize_session=False)
    )

    # 2. Old revoked sessions that have not yet passed their expiry
    revoked_deleted: int = (
        db.query(SessionModel)
        .filter(
            SessionModel.revoked_at != None,   # noqa: E711
            SessionModel.revoked_at <= revoke_cutoff,
            SessionModel.expires_at > now,    # not already deleted above
        )
        .delete(synchronize_session=False)
    )

    return {"sessions_expired": expired_deleted, "sessions_revoked_old": revoked_deleted}


def prune_email_tokens(db: DBSession) -> Dict[str, int]:
    """Delete expired or already-used email verification / password-reset tokens.

    Does NOT commit — caller must commit.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Delete tokens that are expired or have already been consumed
    count: int = (
        db.query(EmailToken)
        .filter(
            (EmailToken.expires_at <= now) | (EmailToken.used_at != None)  # noqa: E711
        )
        .delete(synchronize_session=False)
    )

    return {"email_tokens": count}


def prune_all(db: DBSession) -> Dict[str, int]:
    """Run all pruning tasks and commit.  Safe to call repeatedly (idempotent)."""
    stats: Dict[str, int] = {}
    stats.update(prune_sessions(db))
    stats.update(prune_email_tokens(db))
    db.commit()
    return stats
