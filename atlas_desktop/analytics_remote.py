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
    "impact_analyzed": "impact_completed",
    "graph_opened": "graph_opened",
    "mcp_connected": "mcp_connected",
    "mcp_connect": "mcp_connected",
    "analytics_opted_out": "analytics_opted_out",
}
_ALLOWED_EVENTS = frozenset(_EVENT_MAP.values())
_ALLOWED_PROPERTIES = frozenset({"surface", "outcome", "status", "agent", "workflow", "duration_active_ms", "duration_elapsed_ms"})
_SENSITIVE = re.compile(
    r"(?:[a-z]:\\|\\\\|/(?:users|home|var|etc|private|tmp)/|"
    r"\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b|"
    r"bearer\s+|sb_secret_|service[_-]?role|eyJ[a-z0-9_-]{10,}\.|"
    r"access[_-]?token|secret|password|prompt|"
    r"repo(?:sitory)?(?:[_\s-]*(?:path|name|folder))?|"
    r"file(?:[_\s-]*(?:path|name))|source(?:[_\s-]*code)?|"
    r"symbol(?:[_\s-]*name)?|graph(?:[_\s-]*(?:content|node|edge))|"
    r"impact(?:[_\s-]*(?:path|result))|terminal(?:[_\s-]*output)?|"
    r"windows(?:[_\s-]*user(?:name)?)|user(?:name)?|stack[_-]?trace)",
    re.IGNORECASE,
)
_MAX_QUEUE_EVENTS = 100
_MAX_QUEUE_BYTES = 256 * 1024
_MAX_DELIVERY_ATTEMPTS = 3
_LOCK = threading.Lock()
_FLUSHING = False
# Fail closed for the lifetime of this process if an opt-out write cannot be
# persisted.  This prevents a transient disk error from silently re-enabling
# delivery after the user explicitly disabled analytics.
_LOCAL_OPT_OUT: Optional[bool] = None
_LOCAL_OPT_OUT_PATH: Optional[str] = None


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


def _write_json(path: str, value: Any) -> bool:
    try:
        temporary = f"{path}.tmp"
        with open(temporary, "w", encoding="utf-8") as fh:
            json.dump(value, fh, separators=(",", ":"))
        os.replace(temporary, path)
        return True
    except OSError:
        return False


def analytics_enabled() -> bool:
    """Return whether the local user has not opted out of analytics.

    A missing preferences file means the user never opted out (default on).
    A present-but-unreadable file fails CLOSED: a user who disabled analytics
    must never be silently re-enabled by a corrupted preference."""
    if _LOCAL_OPT_OUT is True and _LOCAL_OPT_OUT_PATH == _preferences_path():
        return False
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
    global _LOCAL_OPT_OUT, _LOCAL_OPT_OUT_PATH
    requested = bool(opted_out)
    preference_path = _preferences_path()
    # Block immediately while the preference is being persisted.  If the
    # write fails, retain this in-memory fail-closed state and report failure
    # so the UI can explain that the choice needs to be retried.
    if requested:
        _LOCAL_OPT_OUT = True
        _LOCAL_OPT_OUT_PATH = preference_path
    persisted = _write_json(preference_path, {"opted_out": requested, "updated_at": int(time.time())})
    if not persisted:
        return {"ok": False, "opted_out": requested, "error": "analytics_preference_unavailable"}
    _LOCAL_OPT_OUT = requested
    _LOCAL_OPT_OUT_PATH = preference_path
    if requested:
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


def _contains_forbidden(value: Any) -> bool:
    """Reject forbidden keys or values at any nesting depth."""
    if isinstance(value, str):
        return bool(_SENSITIVE.search(value))
    if isinstance(value, dict):
        return any(_SENSITIVE.search(str(key)) or _contains_forbidden(child) for key, child in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_forbidden(child) for child in value)
    return False


def _safe_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Return only primitive, allowlisted coarse metadata.

    Nested objects are intentionally discarded rather than flattened.  This
    prevents accidental repository data, source snippets or prompts from
    crossing the local boundary through a future caller.
    """
    if _contains_forbidden(properties):
        return {}
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
    # Delivery-attempt state belongs only to the local bounded outbox. Sending
    # it would violate the frozen desktop contract and turn any retry after a
    # transient failure into a deterministic `invalid_event` response.
    wire_events = [
        {key: value for key, value in event.items() if key != "_delivery_attempts"}
        for event in events
    ]
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"events": wire_events}, separators=(",", ":")).encode("utf-8"),
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
        # An event can be queued after flush() snapshots its batch but before
        # this worker clears _FLUSHING. Its scheduling attempt then sees the
        # active worker and returns. Re-arm delivery here so the last milestone
        # in a session cannot remain stranded until another event occurs.
        if analytics_enabled() and analytics_endpoint() and _load_queue():
            _schedule_flush()


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
    if event == "scan_completed" and properties.get("demo") is True:
        event_name = "sample_scan_completed"
    else:
        event_name = _EVENT_MAP.get(event, event if event in _ALLOWED_EVENTS else "")
    if not event_name:
        return
    if _contains_forbidden(properties):
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
    """Legacy no-op: website clicks never claim a completed installation."""
    return None
