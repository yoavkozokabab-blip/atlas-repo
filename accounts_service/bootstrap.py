"""Atlas Accounts Service — first-run superadmin bootstrap.

The operator sets ``ATLAS_INITIAL_ADMINS`` to a comma-separated list of
email addresses before starting the service for the first time.  On every
startup ``bootstrap_superadmins()`` is called; it promotes any matching
*already-registered* users to superadmin.

Design invariants:
  - Only reads from a privileged env var — no API endpoint triggers this.
  - Idempotent: re-running does not downgrade existing superadmins and does
    not fail if a user is not yet registered.
  - Only *upgrades* (user → admin → superadmin); never downgrades.
  - Callers should remove (or empty) ATLAS_INITIAL_ADMINS from the env after
    the first successful bootstrap to reduce the attack surface.
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session as DBSession

from .config import INITIAL_ADMINS
from .models import AdminAuditLog, User

_logger = logging.getLogger(__name__)

_BOOTSTRAP_ADMIN_ID = "system-bootstrap"
_BOOTSTRAP_ADMIN_EMAIL = "system@bootstrap.internal"


def bootstrap_superadmins(db: DBSession) -> int:
    """Promote INITIAL_ADMINS emails to superadmin role.

    Returns the number of accounts that were promoted in this run.
    Returns 0 when INITIAL_ADMINS is empty or all targets are already superadmin.
    """
    if not INITIAL_ADMINS:
        return 0

    promoted: int = 0
    for raw_email in INITIAL_ADMINS:
        email = raw_email.lower().strip()
        if not email:
            continue

        user: User | None = db.query(User).filter(User.email == email).first()
        if user is None:
            _logger.info(
                "bootstrap_superadmins: %s is not yet registered — will promote on next restart",
                email,
            )
            continue

        if user.role == "superadmin":
            _logger.debug(
                "bootstrap_superadmins: %s is already superadmin — no change",
                email,
            )
            continue

        before_role = user.role
        user.role = "superadmin"
        promoted += 1

        # Write an immutable audit record so the promotion is traceable.
        entry = AdminAuditLog(
            admin_user_id=_BOOTSTRAP_ADMIN_ID,
            admin_email=_BOOTSTRAP_ADMIN_EMAIL,
            action="bootstrap_superadmin",
            target_user_id=user.user_id,
            target_user_email=user.email,
            metadata_={"before_role": before_role, "after_role": "superadmin"},
        )
        db.add(entry)
        _logger.info(
            "bootstrap_superadmins: promoted %s (%s) from %s → superadmin",
            email,
            user.user_id,
            before_role,
        )

    if promoted:
        db.commit()

    return promoted
