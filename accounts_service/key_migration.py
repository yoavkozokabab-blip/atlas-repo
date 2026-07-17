"""v1.0.4 → v1.0.5 signing-key security migration.

The v1.0.4 accounts service signed tokens with a fixed secret that was
exposed publicly. On the first v1.0.5 launch this migration:

* ensures the per-installation signing key exists (created as a side effect
  of importing the security layer),
* revokes every legacy refresh session so no pre-migration refresh token can
  mint new access tokens,
* records a non-secret marker + the active key fingerprint in a small
  ``service_meta`` table.

Access-token trust is invalidated structurally: v1.0.5 tokens must carry the
active key's fingerprint claim (``kfp``) and pass signature under the new
per-install key, so every v1.0.4 token fails validation regardless of this
migration. The session revocation here closes the refresh path.

Properties: idempotent (marker check), retry-safe and interruption-safe (the
revocation and the marker are written in one transaction; a crash before
commit simply reruns the migration on next launch), and preserving — no user,
license, profile, settings, analytics-preference, or unrelated rows are
touched.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from .jwt_secret import current_key_fingerprint

MIGRATION_MARKER = "jwt_key_migration_v105_completed"
_LOG = logging.getLogger(__name__)


def _ensure_meta_table(db: OrmSession) -> None:
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS service_meta ("
            "  key VARCHAR(64) PRIMARY KEY,"
            "  value VARCHAR(255) NOT NULL,"
            "  created_at VARCHAR(40) NOT NULL"
            ")"
        )
    )


def migration_completed(db: OrmSession) -> bool:
    _ensure_meta_table(db)
    row = db.execute(
        text("SELECT value FROM service_meta WHERE key = :k"),
        {"k": MIGRATION_MARKER},
    ).fetchone()
    return row is not None


def run_key_migration(db: OrmSession) -> bool:
    """Run the migration once. Returns True if work was performed."""
    _ensure_meta_table(db)
    if migration_completed(db):
        return False

    now = datetime.now(timezone.utc)
    # Revoke every still-active refresh session. Legacy access tokens are
    # already structurally rejected (new key + kfp claim); this closes the
    # refresh path. Users, licenses, profiles, and analytics preferences are
    # deliberately untouched.
    revoked = db.execute(
        text(
            "UPDATE sessions SET revoked_at = :now, revoked_reason = :reason "
            "WHERE revoked_at IS NULL"
        ),
        {"now": now.replace(tzinfo=None), "reason": "jwt_key_migration_v105"},
    )
    fingerprint = current_key_fingerprint()  # non-secret identifier
    db.execute(
        text(
            "INSERT INTO service_meta (key, value, created_at) "
            "VALUES (:k, :v, :ts)"
        ),
        {"k": MIGRATION_MARKER, "v": f"key_fp={fingerprint}", "ts": now.isoformat()},
    )
    db.commit()
    _LOG.info(
        "jwt key migration v105: revoked %s legacy session(s); marker recorded",
        getattr(revoked, "rowcount", "?"),
    )
    return True
