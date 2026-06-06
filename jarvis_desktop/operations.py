"""Phase 182 — Beta operations foundation (local-only, no intelligence changes)."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import analytics
from .product_info import PRODUCT_VERSION, check_for_update

PIPELINE_VERSION = "1"
_CHANNEL = "beta"
_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _data_dir() -> str:
    from .data_paths import desktop_data_dir

    return desktop_data_dir()


def _operations_dir(data_dir: Optional[str] = None) -> str:
    path = os.path.join(data_dir or _data_dir(), "operations")
    os.makedirs(path, exist_ok=True)
    return path


def _installation_path(data_dir: Optional[str] = None) -> str:
    return os.path.join(_operations_dir(data_dir), "installation.json")


def _crashes_path(data_dir: Optional[str] = None) -> str:
    return os.path.join(_operations_dir(data_dir), "crashes.jsonl")


def _feedback_path(data_dir: Optional[str] = None) -> str:
    legacy = os.path.join(data_dir or _data_dir(), "feedback", "feedback.jsonl")
    if os.path.isfile(legacy):
        return legacy
    return os.path.join(_operations_dir(data_dir), "feedback.jsonl")


def _read_jsonl(path: str, *, limit: int = 200) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]


def _append_jsonl(path: str, row: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _parse_semver(version: str) -> Optional[Tuple[int, int, int]]:
    match = _SEMVER_RE.search(str(version or "").strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


# --------------------------------------------------------------------------
# Installation identity
# --------------------------------------------------------------------------

def get_installation_identity(*, data_dir: Optional[str] = None, touch: bool = True) -> Dict[str, Any]:
    """Stable per-install identifier stored locally (never exported as secret)."""
    path = _installation_path(data_dir)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record: Dict[str, Any]
    try:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
        else:
            record = {}
    except (OSError, json.JSONDecodeError):
        record = {}
    if not record.get("installation_id"):
        record = {
            "installation_id": uuid.uuid4().hex[:16],
            "created_at": now,
            "first_version": PRODUCT_VERSION,
            "channel": _CHANNEL,
        }
    if touch:
        record["last_seen_at"] = now
        record["current_version"] = PRODUCT_VERSION
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(record, fh, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass
    return {
        "ok": True,
        "installation_id": record.get("installation_id"),
        "created_at": record.get("created_at"),
        "last_seen_at": record.get("last_seen_at"),
        "first_version": record.get("first_version"),
        "current_version": record.get("current_version") or PRODUCT_VERSION,
        "channel": record.get("channel") or _CHANNEL,
    }


# --------------------------------------------------------------------------
# Analytics event pipeline
# --------------------------------------------------------------------------

def pipeline_track_event(event: str, **properties: Any) -> Dict[str, Any]:
    """Enrich and persist analytics events with installation identity."""
    name = (event or "").strip()
    if not name:
        return {"ok": False, "error": "Event name required."}
    identity = get_installation_identity(touch=False)
    enriched = {
        "product": properties.pop("product", PRODUCT_VERSION),
        "pipeline_version": PIPELINE_VERSION,
        "installation_id": identity.get("installation_id"),
        "channel": _CHANNEL,
        **{k: v for k, v in properties.items() if v is not None},
    }
    result = analytics.track_event(name, **enriched)
    if name in {"scan_crash", "app_crash"}:
        record_crash(
            name,
            str(enriched.get("message") or enriched.get("error") or name),
            context={k: v for k, v in enriched.items() if k not in {"message", "error"}},
        )
    return result


# --------------------------------------------------------------------------
# Crash registry
# --------------------------------------------------------------------------

def record_crash(
    kind: str,
    message: str,
    *,
    exc_type: str = "",
    context: Optional[Dict[str, Any]] = None,
    data_dir: Optional[str] = None,
) -> Dict[str, Any]:
    row = {
        "crash_id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": str(kind or "unknown")[:64],
        "message": str(message or "")[:2000],
        "exc_type": str(exc_type or "")[:120],
        "installation_id": get_installation_identity(touch=False).get("installation_id"),
        "version": PRODUCT_VERSION,
        "context": dict(context or {}),
    }
    ok = _append_jsonl(_crashes_path(data_dir), row)
    identity = get_installation_identity(touch=False)
    analytics.track_event(
        "crash_recorded",
        product=PRODUCT_VERSION,
        pipeline_version=PIPELINE_VERSION,
        installation_id=identity.get("installation_id"),
        kind=row["kind"],
        crash_id=row["crash_id"],
        message=row["message"][:200],
    )
    return {"ok": ok, "crash_id": row["crash_id"]}


def list_crashes(*, data_dir: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_jsonl(_crashes_path(data_dir), limit=limit)
    rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return rows[:limit]


def crash_summary(*, data_dir: Optional[str] = None) -> Dict[str, Any]:
    rows = list_crashes(data_dir=data_dir, limit=200)
    by_kind: Dict[str, int] = {}
    for row in rows:
        kind = str(row.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "total": len(rows),
        "by_kind": by_kind,
        "latest_at": rows[0].get("at") if rows else None,
        "recent": rows[:10],
    }


# --------------------------------------------------------------------------
# Feedback inbox
# --------------------------------------------------------------------------

def list_feedback(*, data_dir: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_jsonl(_feedback_path(data_dir), limit=limit)
    rows.sort(key=lambda r: r.get("timestamp") or r.get("at") or "", reverse=True)
    return rows[:limit]


def feedback_inbox_summary(*, data_dir: Optional[str] = None) -> Dict[str, Any]:
    rows = list_feedback(data_dir=data_dir, limit=200)
    by_category: Dict[str, int] = {}
    for row in rows:
        cat = str(row.get("category") or "general")
        by_category[cat] = by_category.get(cat, 0) + 1
    return {
        "total": len(rows),
        "by_category": by_category,
        "latest_at": rows[0].get("timestamp") if rows else None,
        "items": rows[:20],
    }


# --------------------------------------------------------------------------
# Token savings dashboard
# --------------------------------------------------------------------------

def _token_totals_from_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    export_tokens = 0
    full_tokens = 0
    minimal_tokens = 0
    delta_tokens = 0
    export_events = 0
    for row in events:
        event = str(row.get("event") or "")
        if event not in {"export_created", "bundle_exported", "session_export_used"}:
            continue
        export_events += 1
        export_tokens += int(row.get("tokens") or row.get("export_tokens") or 0)
        full_tokens += int(row.get("full_export_tokens") or 0)
        minimal_tokens += int(row.get("minimal_export_tokens") or 0)
        delta_tokens += int(row.get("delta_export_tokens") or 0)
    savings_vs_full = 0.0
    if full_tokens and minimal_tokens:
        savings_vs_full = round(100 * (1 - minimal_tokens / full_tokens), 1)
    savings_vs_full_delta = 0.0
    if minimal_tokens and delta_tokens:
        savings_vs_full_delta = round(100 * (1 - delta_tokens / minimal_tokens), 1)
    return {
        "export_events": export_events,
        "active_export_tokens": export_tokens,
        "full_export_tokens_total": full_tokens,
        "minimal_export_tokens_total": minimal_tokens,
        "delta_export_tokens_total": delta_tokens,
        "savings_vs_full_pct": savings_vs_full,
        "savings_minimal_vs_delta_pct": savings_vs_full_delta,
    }


def token_savings_dashboard(
    *,
    data_dir: Optional[str] = None,
    scan_token_savings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    events = analytics._read_events()
    totals = _token_totals_from_events(events)
    scan_est = dict(scan_token_savings or {})
    return {
        "ok": True,
        "local_only": True,
        "from_events": totals,
        "current_scan_estimate": scan_est,
        "note": "Aggregated from local analytics export events and current scan estimate.",
    }


# --------------------------------------------------------------------------
# Update hardening
# --------------------------------------------------------------------------

def check_update_hardened() -> Dict[str, Any]:
    """Validate update metadata before surfacing upgrade prompts."""
    raw = check_for_update()
    result = dict(raw)
    result["trust_level"] = "trusted"
    if not raw.get("configured"):
        result["update_available"] = False
        return result
    if raw.get("check_failed"):
        result["trust_level"] = "unavailable"
        result["update_available"] = False
        return result
    latest = str(raw.get("latest_version") or "").strip()
    current = _parse_semver(PRODUCT_VERSION)
    latest_t = _parse_semver(latest)
    if not latest or latest_t is None or current is None:
        result["trust_level"] = "malformed"
        result["update_available"] = False
        result["error"] = "Update metadata malformed — ignoring remote response."
        return result
    if latest_t < current:
        result["trust_level"] = "malformed"
        result["update_available"] = False
        result["error"] = "Remote version older than current install."
        return result
    if latest_t[0] - current[0] > 1:
        result["trust_level"] = "malformed"
        result["update_available"] = False
        result["error"] = "Remote version major jump too large."
        return result
    channel = str((raw.get("channel") if isinstance(raw, dict) else "") or "").strip().lower()
    if channel and channel not in {_CHANNEL, "beta", "stable"}:
        result["trust_level"] = "malformed"
        result["update_available"] = False
        result["error"] = f"Unsupported update channel: {channel}"
    return result


# --------------------------------------------------------------------------
# Beta insights dashboard
# --------------------------------------------------------------------------

def _admin_enabled() -> bool:
    return os.environ.get("ATLAS_ADMIN", "").strip().lower() in ("1", "true", "yes")


def beta_insights_dashboard(
    *,
    data_dir: Optional[str] = None,
    scan_token_savings: Optional[Dict[str, Any]] = None,
    is_admin: Optional[bool] = None,
) -> Dict[str, Any]:
    admin = _admin_enabled() if is_admin is None else bool(is_admin)
    if not admin:
        return {
            "ok": False,
            "code": "admin_disabled",
            "error": "Beta insights require ATLAS_ADMIN=1 on this machine.",
            "admin_enabled": False,
        }
    identity = get_installation_identity(data_dir=data_dir)
    analytics_summary = analytics.analytics_summary()
    return {
        "ok": True,
        "admin_enabled": True,
        "local_only": True,
        "installation": identity,
        "analytics": analytics_summary,
        "feedback": feedback_inbox_summary(data_dir=data_dir),
        "crashes": crash_summary(data_dir=data_dir),
        "token_savings": token_savings_dashboard(
            data_dir=data_dir,
            scan_token_savings=scan_token_savings,
        ),
        "update": check_update_hardened(),
        "pipeline_version": PIPELINE_VERSION,
    }
