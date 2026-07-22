"""Best-effort, privacy-filtered delivery of Atlas desktop analytics.

The local analytics log remains the source of truth for the application.  This
module mirrors a small allowlisted subset to the Atlas website *only* from a
packaged build (or when a test explicitly configures an endpoint).  It never
blocks a product workflow, never reads repository state, and keeps a bounded
local outbox for short offline periods.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from .data_paths import desktop_data_dir

_EVENT_MAP = {
    # This is intentionally a small product-milestone contract, never a UI
    # activity stream.  Local analytics retains its separate local record.
    "app_started": "desktop_launched",
    "sample_scan_completed": "sample_scan_completed",
    "scan_completed": "real_repo_scan_completed",
    "scan_failed": "scan_failed",
    "what_breaks_generated": "impact_completed",
    "graph_opened": "graph_opened",
    "mcp_connected": "mcp_connected",
    "account_create_started": "account_create_started",
    "account_signup_completed": "account_create_success",
    "account_create_failed": "account_create_failed",
    "login_started": "login_started",
    "account_login_completed": "login_success",
    "login_failed": "login_failed",
    "logout": "logout",
    "account_deleted": "account_deleted",
    "analytics_opted_out": "analytics_opted_out",
    "app_first_run": "desktop_installed",
}
_ALLOWED_EVENTS = frozenset(_EVENT_MAP.values())
_ALLOWED_PROPERTIES = frozenset({"surface", "outcome", "status", "agent", "workflow", "duration_active_ms", "duration_elapsed_ms"})
_SENSITIVE = re.compile(r"(?:[a-z]:\\|\\\\|/(?:users|home|var|etc|private|tmp)/|bearer\s+|secret|token|password|prompt|repo(?:sitory)?|path|file(?:name)?)", re.IGNORECASE)
_MAX_QUEUE_EVENTS = 100
_MAX_QUEUE_BYTES = 256 * 1024
_MAX_DELIVERY_ATTEMPTS = 3
_LOCK = threading.Lock()
_FLUSHING = False


def _operations_dir() -> str:
    path = os.path.join(desktop_data_dir(), "operations")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _queue_path() -> str:
    return os.path.join(_operations_dir(), "analytics-outbox.json")


def _preferences_path() -> str:
    return os.path.join(_operations_dir(), "analytics-preferences.json")


def _diagnostics_path() -> str:
    return os.path.join(_operations_dir(), "analytics-diagnostics.json")


def _read_json(path: str, fallback: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
        return value
    except (OSError, ValueError, TypeError):
        return fallback


def _write_json(path: str, value: Any) -> None:
    try:
        temporary = f"{path}.tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(value, fh, separators=(",", ":"))
        os.replace(temporary, path)
    except OSError:
        pass


def analytics_enabled() -> bool:
    """Return whether the local user has not opted out of analytics.

    A missing preferences file means the user never opted out (default on).
    A present-but-unreadable file fails CLOSED: a user who disabled analytics
    must never be silently re-enabled by a corrupted preference."""
    path = _preferences_path()
    try:
        if not os.path.exists(path):
            return True
    except OSError:
        return False
    value = _read_json(path, None)
    if not isinstance(value, dict):
        return False
    return value.get("opted_out") is not True


def set_analytics_opt_out(opted_out: bool) -> Dict[str, Any]:
    """Persist the explicit local opt-out without contacting the network.

    Opting out also drops any queued-but-unsent events so the choice is
    retroactive: nothing already captured can still be delivered.
    """
    _write_json(_preferences_path(), {"opted_out": bool(opted_out), "updated_at": int(time.time())})
    if opted_out:
        with _LOCK:
            try:
                # Remove the outbox entirely: nothing already captured may
                # still be delivered, and no queue artifact should remain.
                os.remove(_queue_path())
            except OSError:
                pass
    return {"ok": True, "opted_out": bool(opted_out)}


def analytics_endpoint() -> str:
    explicit = (os.environ.get("ATLAS_ANALYTICS_ENDPOINT") or "").strip().rstrip("/")
    if explicit:
        return explicit
    # Source/dev and tests do not silently send network traffic. Packaged Atlas
    # uses the same canonical authority as desktop authentication.
    if not getattr(sys, "frozen", False):
        return ""
    from .accounts_client import web_base

    return f"{web_base()}/api/analytics/desktop-events"


def _safe_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Return only primitive, allowlisted coarse metadata.

    Nested objects are intentionally discarded rather than flattened.  This
    prevents accidental repository data, source snippets or prompts from
    crossing the local boundary through a future caller.
    """
    output: Dict[str, Any] = {}
    for key, value in properties.items():
        if key not in _ALLOWED_PROPERTIES or value is None:
            continue
        if isinstance(value, bool):
            output[key] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            output[key] = max(0, min(int(value), 86_400_000))
        elif isinstance(value, str):
            cleaned = value.strip()[:80]
            if cleaned and not _SENSITIVE.search(cleaned):
                output[key] = cleaned
    return output


def _record_delivery_result(*, status: str, accepted: int = 0, rejected: int = 0, retried: int = 0) -> None:
    """Keep diagnostics operational and non-sensitive: no payloads or tokens."""
    current = _read_json(_diagnostics_path(), {})
    if not isinstance(current, dict):
        current = {}
    current["accepted"] = int(current.get("accepted") or 0) + accepted
    current["rejected"] = int(current.get("rejected") or 0) + rejected
    current["retries"] = int(current.get("retries") or 0) + retried
    current["last_status_class"] = status[:24]
    current["updated_at"] = int(time.time())
    _write_json(_diagnostics_path(), current)


def diagnostics() -> Dict[str, Any]:
    """Return safe delivery counters for local diagnostics and tests."""
    value = _read_json(_diagnostics_path(), {})
    return value if isinstance(value, dict) else {}


def _load_queue() -> List[Dict[str, Any]]:
    value = _read_json(_queue_path(), [])
    return value if isinstance(value, list) else []


def _save_queue(events: List[Dict[str, Any]]) -> None:
    trimmed: List[Dict[str, Any]] = []
    total = 2
    for event in reversed(events[-_MAX_QUEUE_EVENTS:]):
        encoded = json.dumps(event, separators=(",", ":")).encode("utf-8")
        if total + len(encoded) > _MAX_QUEUE_BYTES:
            break
        trimmed.append(event)
        total += len(encoded)
    _write_json(_queue_path(), list(reversed(trimmed)))


def _enqueue(event: Dict[str, Any]) -> None:
    with _LOCK:
        queue = _load_queue()
        queue.append(event)
        _save_queue(queue)


def _post_batch(endpoint: str, events: List[Dict[str, Any]]) -> tuple[bool, str]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"events": events}, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "AtlasDesktop/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            status = int(response.status)
            return 200 <= status < 300, f"http_{status // 100}xx"
    except urllib.error.HTTPError as exc:
        return False, f"http_{int(exc.code) // 100}xx"
    except (OSError, urllib.error.URLError):
        return False, "network_error"


def flush() -> bool:
    """Attempt one bounded outbox delivery.  Returns false on any failure."""
    endpoint = analytics_endpoint()
    if not endpoint or not analytics_enabled():
        return False
    with _LOCK:
        queue = _load_queue()
        batch = queue[:20]
    if not batch:
        return True
    posted, status = _post_batch(endpoint, batch)
    if not posted:
        with _LOCK:
            latest = _load_queue()
            failed = {str(item.get("eventId")) for item in batch}
            retained: List[Dict[str, Any]] = []
            dropped = 0
            for item in latest:
                if str(item.get("eventId")) not in failed:
                    retained.append(item)
                    continue
                attempts = int(item.get("_delivery_attempts") or 0) + 1
                if attempts >= _MAX_DELIVERY_ATTEMPTS:
                    dropped += 1
                    continue
                item["_delivery_attempts"] = attempts
                retained.append(item)
            _save_queue(retained)
        _record_delivery_result(status=status, rejected=dropped, retried=len(batch) - dropped)
        return False
    with _LOCK:
        latest = _load_queue()
        delivered = {str(item.get("eventId")) for item in batch}
        _save_queue([item for item in latest if str(item.get("eventId")) not in delivered])
    _record_delivery_result(status=status, accepted=len(batch))
    return True


def _flush_async() -> None:
    global _FLUSHING
    try:
        flush()
    finally:
        with _LOCK:
            _FLUSHING = False


def _schedule_flush() -> None:
    global _FLUSHING
    with _LOCK:
        if _FLUSHING:
            return
        _FLUSHING = True
    threading.Thread(target=_flush_async, name="atlas-analytics", daemon=True).start()


def track_pipeline_event(event: str, *, installation_id: Optional[str], app_version: str, build_commit: str, properties: Dict[str, Any]) -> None:
    """Queue one allowlisted event without exposing product data or blocking."""
    if not analytics_enabled():
        return
    event_name = _EVENT_MAP.get(event, event if event in _ALLOWED_EVENTS else "")
    if not event_name:
        return
    identity = str(installation_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,160}", identity):
        return
    _enqueue({
        "eventId": str(uuid.uuid4()),
        "eventName": event_name,
        "installationId": identity,
        "sessionId": f"desktop-{os.getpid()}-{int(time.time() // 60)}",
        "appVersion": str(app_version or "")[:80],
        "buildCommit": str(build_commit or "")[:40],
        "properties": _safe_properties(properties),
    })
    _schedule_flush()


def record_first_run(*, installation_id: Optional[str], app_version: str, build_commit: str) -> None:
    """Queue exactly one first-successful-run event for a local installation."""
    path = os.path.join(_operations_dir(), "analytics-first-run.json")
    state = _read_json(path, {})
    if state.get("recorded") is True or not analytics_enabled():
        return
    track_pipeline_event("app_first_run", installation_id=installation_id, app_version=app_version, build_commit=build_commit, properties={})
    _write_json(path, {"recorded": True, "at": int(time.time())})
