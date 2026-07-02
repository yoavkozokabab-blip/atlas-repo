"""Production billing sync from Vercel/Supabase into the accounts service."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from . import config
from .models import License, User


class BillingSyncError(RuntimeError):
    """Raised when billing sync is required but the remote lookup fails."""


def _parse_remote_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _accounts_plan(remote_plan: str, remote_status: str) -> str:
    # The accounts service models trial as a license status, not a plan enum.
    if remote_plan in {"trial", "pro"} or remote_status == "trial":
        return "pro"
    if remote_plan in {"free", "beta", "enterprise"}:
        return remote_plan
    return "free"


def _accounts_status(remote_status: str, valid: bool) -> str:
    status = (remote_status or "").lower()
    if status in {"active", "trial", "expired", "past_due", "canceled", "cancelled", "suspended"}:
        return "canceled" if status == "cancelled" else status
    return "active" if valid else "expired"


def apply_remote_license(user: User, remote: dict[str, Any], db: Session) -> License:
    status = _accounts_status(str(remote.get("status") or ""), bool(remote.get("valid")))
    plan = _accounts_plan(str(remote.get("plan") or ""), status)
    lic = user.license
    if not lic:
        lic = License(user_id=user.user_id, plan=plan, status=status, max_devices=1)
        db.add(lic)
    lic.plan = plan
    lic.status = status
    lic.max_devices = int(remote.get("max_devices") or (3 if plan == "pro" else 1))
    lic.expires_at = _parse_remote_time(remote.get("valid_until") or remote.get("trial_end"))
    lic.notes = "synced_from_stripe_billing"
    db.commit()
    db.refresh(lic)
    return lic


def _billing_lookup(email: str) -> Optional[dict[str, Any]]:
    if not config.BILLING_LICENSE_URL or not config.BILLING_SYNC_SECRET:
        return None
    payload = json.dumps({"email": email}).encode("utf-8")
    req = urllib.request.Request(
        config.BILLING_LICENSE_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-License-Sync-Secret": config.BILLING_SYNC_SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=config.BILLING_SYNC_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        if config.BILLING_SYNC_REQUIRED:
            raise BillingSyncError(f"Billing license lookup failed with HTTP {exc.code}") from exc
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        if config.BILLING_SYNC_REQUIRED:
            raise BillingSyncError("Billing license lookup failed") from exc
        return None
    return data.get("license") if data.get("ok") else None


def sync_billing_license(user: User, db: Session) -> Optional[License]:
    remote = _billing_lookup(user.email)
    if not remote:
        if config.BILLING_SYNC_REQUIRED:
            raise BillingSyncError("No active billing license found")
        return None
    remote_email = str(remote.get("email") or "").strip().lower()
    if remote_email != user.email.strip().lower():
        if config.BILLING_SYNC_REQUIRED:
            raise BillingSyncError("Billing license email mismatch")
        return None
    return apply_remote_license(user, remote, db)
