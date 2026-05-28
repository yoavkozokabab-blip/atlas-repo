"""Confirmation framework for destructive or system actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config import CONFIRMATION_TIMEOUT_SECONDS


@dataclass
class PendingConfirmation:
    confirmation_id: str
    action_name: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def expired(self) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return elapsed > CONFIRMATION_TIMEOUT_SECONDS


_store: PendingConfirmation | None = None


def create_confirmation(action_name: str, payload: dict[str, Any]) -> str:
    """Store a pending confirmation and return its id."""
    global _store
    confirmation_id = str(uuid.uuid4())[:8]
    _store = PendingConfirmation(
        confirmation_id=confirmation_id,
        action_name=action_name,
        payload=payload,
    )
    return confirmation_id


def get_pending_confirmation() -> PendingConfirmation | None:
    if _store is None:
        return None
    if _store.expired():
        cancel(_store.confirmation_id)
        return None
    return _store


def confirm(confirmation_id: str) -> PendingConfirmation | None:
    pending = get_pending_confirmation()
    if pending is None or pending.confirmation_id != confirmation_id:
        return None
    global _store
    confirmed = pending
    _store = None
    return confirmed


def cancel(confirmation_id: str | None = None) -> bool:
    global _store
    if _store is None:
        return False
    if confirmation_id is None or _store.confirmation_id == confirmation_id:
        _store = None
        return True
    return False


def clear_all() -> None:
    global _store
    _store = None


CONFIRM_PHRASES = frozenset(
    {
        "yes",
        "y",
        "confirm",
        "confirmed",
        "approve",
        "כן",
        "אישור",
        "תאשר",
        "בצע",
    }
)

CANCEL_PHRASES = frozenset(
    {
        "no",
        "n",
        "cancel",
        "abort",
        "stop",
        "לא",
        "בטל",
        "ביטול",
    }
)


def is_confirm_phrase(text: str) -> bool:
    return text.strip().lower() in CONFIRM_PHRASES


def is_cancel_phrase(text: str) -> bool:
    return text.strip().lower() in CANCEL_PHRASES
