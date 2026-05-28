"""Read-only email/calendar providers (Phase 67) — no send/update/delete."""

from __future__ import annotations

import json
from pathlib import Path

from config import INTEGRATION_FIXTURES_DIR
from providers.daily_summary_provider import DailySummary

_REAL_EMAIL_BANNER = "REAL READONLY | gmail_readonly | NO MUTATIONS"
_REAL_CAL_BANNER = "REAL READONLY | gcal_readonly | NO MUTATIONS"


def _load_fixture(name: str) -> dict:
    path = INTEGRATION_FIXTURES_DIR / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


class ReadonlyEmailProvider:
    """Reads inbox data from local credential/fixture store (read-only)."""

    def summarize_last(self, count: int) -> DailySummary:
        data = _load_fixture("gmail_readonly_inbox.json")
        messages = data.get("messages") or []
        urgent = [m.get("subject", "") for m in messages if m.get("urgent")][:10]
        waiting = [m.get("subject", "") for m in messages if m.get("waiting_on_me")][:10]
        schedule = [f"Read {min(count, len(messages))} messages from readonly store."]
        risks = list(data.get("risks") or [])[:8]
        actions = list(data.get("recommended_actions") or [])[:8]
        if not messages:
            urgent = ["(fixture empty — connect OAuth or add gmail_readonly_inbox.json)"]
        return DailySummary(
            urgent=urgent or ["No urgent items in readonly inbox."],
            waiting_on_me=waiting or ["No pending replies in readonly inbox."],
            schedule=schedule,
            risks=risks or ["Readonly inbox loaded; review threads manually."],
            recommended_actions=actions or ["Review readonly inbox summary."],
        )

    def format_banner(self) -> str:
        return _REAL_EMAIL_BANNER


class ReadonlyCalendarProvider:
    """Reads calendar data from local credential/fixture store (read-only)."""

    def summarize_day(self) -> DailySummary:
        data = _load_fixture("gcal_readonly_calendar.json")
        events = data.get("events") or []
        schedule = [
            f"{e.get('time', '??:??')} {e.get('title', 'Event')}" for e in events[:20]
        ]
        return DailySummary(
            urgent=list(data.get("urgent") or [])[:8],
            waiting_on_me=list(data.get("waiting_on_me") or [])[:8],
            schedule=schedule or ["No events in readonly calendar fixture."],
            risks=list(data.get("risks") or [])[:8],
            recommended_actions=list(data.get("recommended_actions") or [])[:8],
        )

    def find_conflicts(self) -> DailySummary:
        data = _load_fixture("gcal_readonly_calendar.json")
        conflicts = data.get("conflicts") or []
        return DailySummary(
            urgent=[c.get("detail", str(c)) for c in conflicts[:5]] or ["No conflicts in readonly calendar."],
            waiting_on_me=list(data.get("waiting_on_me") or [])[:5],
            schedule=[f"Conflict checks: {len(conflicts)} found."],
            risks=list(data.get("risks") or [])[:5],
            recommended_actions=list(data.get("recommended_actions") or [])[:5],
        )

    def format_banner(self) -> str:
        return _REAL_CAL_BANNER


def credentials_available(mode: str) -> bool:
    """True when readonly mode has fixture or OAuth credential file."""
    if mode == "gmail_readonly":
        return (INTEGRATION_FIXTURES_DIR / "gmail_readonly_inbox.json").is_file() or (
            INTEGRATION_FIXTURES_DIR / "gmail_credentials.json"
        ).is_file()
    if mode == "gcal_readonly":
        return (INTEGRATION_FIXTURES_DIR / "gcal_readonly_calendar.json").is_file() or (
            INTEGRATION_FIXTURES_DIR / "gcal_credentials.json"
        ).is_file()
    return False
