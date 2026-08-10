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
    # beta.2 funnel. Without these we can count launches and finished scans but
    # cannot tell where anyone stops, which agent they use, or whether Atlas
    # ever did something useful for them.
    "onboarding_local_mode_selected": "onboarding_local_mode_selected",
    "repository_selected": "repository_selected",
    "scan_started": "scan_started",
    "mcp_configured": "mcp_configured",
    "mcp_initialize_success": "mcp_initialize_success",
    "atlas_tool_called": "atlas_tool_called",
    "first_value_reached": "first_value_reached",
    "feedback_opened": "feedback_opened",
    "feedback_submitted": "feedback_submitted",
}
_ALLOWED_EVENTS = frozenset(_EVENT_MAP.values())
_ALLOWED_PROPERTIES = frozenset({
    "surface", "outcome", "status", "agent", "workflow",
    "duration_active_ms", "duration_elapsed_ms",
    # beta.2 additions. Every one is a closed enum or a coarse bucket; none can
    # carry a name, path, identifier or free text.
    "tool_name", "error_code", "repo_size_bucket", "category",
})

# Value-level allowlists. Key filtering alone is not enough: a caller could put
# a repository path in a permitted key. Anything not in these sets is replaced
# with a safe sentinel or dropped, never forwarded.
_AGENTS = frozenset({"claude", "cursor", "codex", "other"})
_REPO_SIZE_BUCKETS = frozenset({"tiny", "small", "medium", "large", "very_large"})
_ERROR_CODES = frozenset({
    "permission_denied", "invalid_repository", "parser_failure",
    "index_failure", "cancelled", "disk_failure", "unknown_safe",
})
_FEEDBACK_CATEGORIES = frozenset({
    "general", "bug", "feature", "question", "performance", "accuracy",
})
# The 18 MCP tools this build exposes. An unknown tool name is dropped rather
# than forwarded, so a renamed or injected tool cannot leak through.
_TOOL_NAMES = frozenset({
    "atlas_scan_repo", "atlas_get_codebase_map", "atlas_repo_summary",
    "atlas_get_architecture", "atlas_get_dependency_graph", "atlas_find_relevant_files",
    "atlas_build_context_pack", "atlas_what_breaks", "atlas_get_impact_analysis",
    "atlas_plan_change", "atlas_get_change_plan", "atlas_root_cause",
    "atlas_find_file", "atlas_repo_health", "atlas_export_for_claude",
    "atlas_export_for_cursor", "atlas_export_for_codex", "atlas_health",
})
# The pre-existing free-text properties are closed here too. A permitted key
# was previously a licence to carry any string that dodged the sensitive-value
# regex, so a filename like "billing_service.py" or a source snippet could ride
# out in `surface` or `workflow`. Every string property is now a closed set.
_SURFACES = frozenset({
    "desktop", "first_run", "workbench", "home", "graph", "impact", "debug",
    "plan", "memory", "files", "agents", "diagnostics", "settings", "support", "other",
})
_WORKFLOWS = frozenset({
    "scan", "impact", "debug", "plan", "export", "understanding", "memory", "other",
})
_OUTCOMES = frozenset({"success", "failure"})
_STATUSES = frozenset({"success", "failure", "cancelled"})

_ENUM_PROPERTIES: Dict[str, tuple] = {
    # property -> (allowed values, fallback or None to drop)
    "agent": (_AGENTS, "other"),
    "repo_size_bucket": (_REPO_SIZE_BUCKETS, None),
    "error_code": (_ERROR_CODES, "unknown_safe"),
    "category": (_FEEDBACK_CATEGORIES, "general"),
    "tool_name": (_TOOL_NAMES, None),
    "surface": (_SURFACES, "other"),
    "workflow": (_WORKFLOWS, "other"),
    "outcome": (_OUTCOMES, None),
    "status": (_STATUSES, None),
}
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


def _forbidden_in_payload(properties: Dict[str, Any]) -> bool:
    """Whether an event must be dropped outright rather than sanitized.

    The blunt version of this check scanned every key and value against the
    sensitive-word pattern, which contains a bare `repo`. That silently
    destroyed the entire `repository_selected` and `scan_started` events,
    because their own property is called `repo_size_bucket` and one of the
    error codes is `invalid_repository` - the funnel would have looked empty
    with no error anywhere.

    So: a key we defined is trusted as a name. Its value is trusted only when
    the property is enum-constrained, because then it can only ever be one of
    our own terms. Everything else is still scanned, and any hit kills the
    whole event rather than being quietly stripped.
    """
    for key, value in properties.items():
        if key not in _ALLOWED_PROPERTIES:
            if _SENSITIVE.search(str(key)) or _contains_forbidden(value):
                return True
            continue
        # The exemption is only for plain strings, which enum membership fully
        # constrains. A dict/list under an enum key is still scanned, so
        # `{"surface": {"path": "C:\\..."}}` keeps killing the whole event.
        if key in _ENUM_PROPERTIES and isinstance(value, str):
            continue
        if _contains_forbidden(value):
            return True
    return False


def _safe_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Return only primitive, allowlisted coarse metadata.

    Nested objects are intentionally discarded rather than flattened.  This
    prevents accidental repository data, source snippets or prompts from
    crossing the local boundary through a future caller.
    """
    if _forbidden_in_payload(properties):
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
            if not cleaned:
                continue
            enum = _ENUM_PROPERTIES.get(key)
            if enum is None:
                # Free-text property: the word filter is the only defence.
                if _SENSITIVE.search(cleaned):
                    continue
                output[key] = cleaned
                continue
            # Enum property: membership is strictly stronger than the word
            # filter, and the filter would reject our own terms - it contains a
            # bare `repo`, which matches the legitimate code `invalid_repository`.
            allowed, fallback = enum
            # A value outside the closed set is never forwarded verbatim: it is
            # either mapped to a sentinel or dropped. This is what stops a
            # repository name arriving in `tool_name` or a raw exception string
            # arriving in `error_code`.
            normalized = cleaned.lower()
            if normalized in allowed:
                output[key] = normalized
            elif fallback is not None:
                output[key] = fallback
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
    if _forbidden_in_payload(properties):
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


def _first_value_path() -> str:
    return os.path.join(_operations_dir(), "first-value.json")


def first_value_reached() -> bool:
    """Whether this installation has already recorded its first value."""
    value = _read_json(_first_value_path(), None)
    return isinstance(value, dict) and value.get("reached") is True


def mark_first_value(*, agent: str = "", tool_name: str = "") -> bool:
    """Record the first successful Atlas tool execution, exactly once.

    `first_value_reached` is the single number that says whether Atlas actually
    did something useful for someone, so it must not be inflated by restarts or
    by a user running a second tool. The marker file makes it idempotent across
    process restarts; a write failure fails CLOSED (returns False, no event) so
    a disk problem can never turn one install into a stream of first values.

    Returns True only on the transition, i.e. only when an event should be sent.
    """
    with _LOCK:
        if first_value_reached():
            return False
        stored = _write_json(_first_value_path(), {
            "reached": True,
            "at": int(time.time()),
            # Coarse context only, and only from closed enums.
            "agent": str(agent or "")[:16],
            "tool_name": str(tool_name or "")[:64],
        })
        return bool(stored)
