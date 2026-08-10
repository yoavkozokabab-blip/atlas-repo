"""Phase 182 / 182A — Beta operations foundation (local-only, no intelligence changes)."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from . import analytics, analytics_remote
from .product_info import PRODUCT_VERSION, build_commit as _build_commit, check_for_update

PIPELINE_VERSION = "1"
_CHANNEL = "beta"
_SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# --------------------------------------------------------------------------
# P0-1  Analytics sanitization constants (182A)
# --------------------------------------------------------------------------

# Fields accepted from external callers via /api/analytics/event.
_ALLOWED_USER_FIELDS = frozenset({
    "event", "event_type", "timestamp", "duration_ms", "token_count",
    "file_count", "repo_language", "workflow_type", "success", "surface", "screen",
    "duration_active_ms", "duration_elapsed_ms",
    # 1.0.6-beta.2 launch funnel. This sanitizer runs BEFORE analytics_remote,
    # so a property missing here is silently stripped and the funnel dimension
    # arrives empty - which is exactly how beta.1 lost the MCP client name.
    # Each of these is a closed enum, enforced again downstream and a third
    # time server-side.
    "agent", "workflow", "outcome", "status",
    "tool_name", "error_code", "repo_size_bucket", "category",
})

# Fields added by the pipeline itself — always permitted.
_SYSTEM_FIELDS = frozenset({
    "installation_id", "pipeline_version", "channel", "product",
    "ts", "at", "version", "crash_id", "kind", "exc_type",
    # aggregate / numeric fields emitted by internal scan / export paths
    "files", "modules", "edges", "symbols", "duration_sec", "duration_s",
    "cache_hit", "ok", "tokens", "export_tokens", "full_export_tokens",
    "minimal_export_tokens", "delta_export_tokens", "bytes", "message",
})

_MAX_FIELD_LEN = 256
_MAX_EVENT_BYTES = 4 * 1024  # 4 KB

# Patterns that signal source code, prompts, or repository export content
# embedded in an analytics field value.  Deliberately no ^ anchors so they
# fire on substrings (a field value is rarely multi-line, but may contain an
# injected snippet anywhere in the string).
_SOURCE_CODE_RE = re.compile(
    # ── code fences & markdown ──────────────────────────────────────────────
    r"```"
    # ── Python ──────────────────────────────────────────────────────────────
    r"|\bdef [a-zA-Z_]\w*\s*\("          # function definition
    r"|\bclass [A-Za-z_]\w*[\s:(]"       # class declaration
    r"|\bimport [a-zA-Z_][\w.]+"         # bare import
    r"|\bfrom [a-zA-Z_][\w.]+ import\b"  # from … import
    r"|\bif __name__\s*=="               # main guard
    # ── JavaScript / TypeScript ─────────────────────────────────────────────
    r"|function\s+[a-zA-Z_]\w*\s*\("    # named function
    r"|\bconst\s+\w+\s*="               # const assignment
    r"|\blet\s+\w+\s*="                 # let assignment
    r"|\bvar\s+\w+\s*="                 # var assignment
    r"|=>\s*\{"                          # arrow function body
    r"|console\.log\s*\("               # debug call
    r"|require\s*\(['\"]"               # CommonJS require
    # ── Prompt / LLM injection patterns ────────────────────────────────────
    r"|\bYou are an? "                  # system-prompt opener
    r"|\bAs an AI\b"                    # LLM self-description
    r"|\bHuman:\s"                      # conversation turn marker
    r"|\bAssistant:\s"                  # conversation turn marker
    r"|<\|im_start\|>"                  # ChatML format
    r"|\[INST\]"                        # Llama instruction tag
    r"|\[/INST\]"
    r"|\bignore previous instructions\b"  # prompt injection
    # ── Atlas export / repository content ───────────────────────────────────
    r"|ATLAS_REPOSITORY_MEMORY"
    r"|## Repository"
    r"|# ==+\s*\w"                      # section divider from exports
)

# --------------------------------------------------------------------------
# P0-2  Crash / secret redaction constants (182A)
# --------------------------------------------------------------------------

# Single compiled pattern to redact all known secret token shapes.
# Compiled with IGNORECASE so bearer/jwt/authorization variants are caught
# regardless of casing; the specific token prefixes (ghp_, sk-, …) are
# effectively case-insensitive too which is a safe over-catch.
_SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9_\-]+"                          # Anthropic key
    r"|\bsk-[A-Za-z0-9_\-]{8,}"                        # OpenAI / generic sk- key
    r"|ghp_[A-Za-z0-9]+"                               # GitHub PAT (classic)
    r"|github_pat_[A-Za-z0-9_]+"                       # GitHub fine-grained PAT
    r"|ghs_[A-Za-z0-9]+"                               # GitHub server token
    r"|xoxb-[A-Za-z0-9\-]+"                            # Slack bot token
    r"|xoxp-[A-Za-z0-9\-]+"                            # Slack user token
    r"|eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*"  # JWT
    r"|\bbearer\s+[A-Za-z0-9_\-\.]+"                   # Bearer <token>
    r"|\bjwt\s*[=:]\s*\S+"                             # jwt=value
    r"|authorization\s*[=:]\s*\S+"                     # Authorization: value
    r"|(?:api[_\-]?key|access[_\-]?token|refresh[_\-]?token"
    r"|auth[_\-]?token|secret(?:[_\-]?key)?|client[_\-]?secret"
    r"|private[_\-]?key|token)\s*[=:]\s*\S+",          # generic key=value
    re.IGNORECASE,
)

# Redact absolute filesystem paths (Windows, Linux, macOS) to prevent
# leaking usernames embedded in path components.
_PATH_RE = re.compile(
    r"[A-Za-z]:\\[^\s\"'\r\n]+"                         # Windows  C:\Users\bob\...
    r"|/(?:home|Users)/[^\s\"'\r\n/]+(?:/[^\s\"'\r\n]*)?"  # POSIX /home/bob/...
    r"|/(?:tmp|var|private|opt)/[^\s\"'\r\n]*"          # other POSIX prefixes
)


def _data_dir() -> str:
    from .data_paths import desktop_data_dir

    return desktop_data_dir()


def _operations_dir(data_dir: Optional[str] = None) -> str:
    path = os.path.join(data_dir or _data_dir(), "operations")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        # A read-only or denied data dir must never break scans/health — the
        # writers below already tolerate a missing directory (telemetry just
        # degrades instead).
        pass
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
# P0-1  Analytics sanitization (182A)
# --------------------------------------------------------------------------

def _scrub_value(v: Any) -> Any:
    """Enforce field-level safety for a single analytics value."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    s = str(v)[:_MAX_FIELD_LEN]
    if _SOURCE_CODE_RE.search(s):
        return "[redacted-content]"
    if _SECRET_RE.search(s):
        return "[redacted-secret]"
    return s


def sanitize_analytics_payload(
    event: str,
    properties: Dict[str, Any],
    *,
    for_external: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    """
    Sanitize an analytics event before persistence.

    for_external=True  — external callers (/api/analytics/event): strip to
                         the user-allowed field whitelist.
    for_external=False — internal pipeline events: allow all system fields,
                         still enforce size + secret/source-code redaction.

    Returns (event_name, sanitized_properties).
    """
    name = (event or "").strip()[:128]

    allowed = (_ALLOWED_USER_FIELDS | _SYSTEM_FIELDS) if not for_external else _ALLOWED_USER_FIELDS

    clean: Dict[str, Any] = {}
    for k, v in properties.items():
        if for_external and k not in allowed:
            continue  # silently drop disallowed fields from external callers
        if not for_external and k in _SYSTEM_FIELDS:
            # system fields: scrub but preserve
            clean[k] = _scrub_value(v)
            continue
        if for_external and k in _ALLOWED_USER_FIELDS:
            clean[k] = _scrub_value(v)
            continue
        # internal non-system fields: apply scrub
        clean[k] = _scrub_value(v)

    # Hard size limit: if still over 4 KB, keep only system fields + event.
    payload = json.dumps({"event": name, **clean}, ensure_ascii=False)
    if len(payload.encode()) > _MAX_EVENT_BYTES:
        clean = {k: v for k, v in clean.items() if k in _SYSTEM_FIELDS}

    return name, clean


# --------------------------------------------------------------------------
# P0-2  Crash text redaction (182A)
# --------------------------------------------------------------------------

def _sanitize_crash_text(text: str) -> str:
    """Redact secrets and absolute paths from crash message text."""
    if not text:
        return text
    out = _SECRET_RE.sub("[redacted-secret]", text)
    out = _PATH_RE.sub("[path-redacted]", out)
    return out


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
    # Only accept the UUIDv4 generated by Atlas.  A hand-edited, migrated, or
    # corrupted value must not become a stable cross-user/device identifier.
    installation_id = str(record.get("installation_id") or "").strip()
    generated = False
    try:
        parsed_id = uuid.UUID(installation_id)
        valid_installation_id = parsed_id.version == 4 and str(parsed_id) == installation_id.lower()
    except (ValueError, AttributeError):
        valid_installation_id = False
    if not valid_installation_id:
        generated = True
        record = {
            "installation_id": str(uuid.uuid4()),
            "created_at": now,
            "first_version": PRODUCT_VERSION,
            "channel": _CHANNEL,
        }
    if touch:
        record["last_seen_at"] = now
        record["current_version"] = PRODUCT_VERSION
    if touch or generated:
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


def get_system_identity(*, data_dir: Optional[str] = None) -> Dict[str, Any]:
    """Spec-aligned identity for GET /api/system/identity."""
    raw = get_installation_identity(data_dir=data_dir)
    return {
        "ok": True,
        "installation_id": raw.get("installation_id"),
        "atlas_version": PRODUCT_VERSION,
        "build_commit": _build_commit(),
        "first_launch": raw.get("created_at"),
        "last_launch": raw.get("last_seen_at"),
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
    # P0-1: internal-path sanitization (size + secret/source-code scrub, no whitelist).
    _, safe_props = sanitize_analytics_payload(name, properties, for_external=False)
    enriched = {
        "product": safe_props.pop("product", PRODUCT_VERSION),
        "pipeline_version": PIPELINE_VERSION,
        "installation_id": identity.get("installation_id"),
        "channel": _CHANNEL,
        **{k: v for k, v in safe_props.items() if v is not None},
    }
    result = analytics.track_event(name, **enriched)
    # Delivery is deliberately fire-and-forget. The local log above remains
    # available even when the network, website collector, or Supabase is down.
    try:
        analytics_remote.track_pipeline_event(
            name,
            installation_id=identity.get("installation_id"),
            app_version=PRODUCT_VERSION,
            build_commit=_build_commit(),
            properties=safe_props,
        )
    except Exception:
        # Remote analytics cannot change the result of a local product action.
        pass
    # Accounts remain disabled in the analytics-only RC. Do not mirror product
    # telemetry to the legacy accounts service or require AtlasAccounts.exe.
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
    # P0-2: redact secrets and paths before storing.
    safe_message = _sanitize_crash_text(str(message or ""))[:500]
    safe_exc_type = str(exc_type or "")[:120]
    row = {
        "crash_id": uuid.uuid4().hex[:12],
        "ts": time.time(),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": str(kind or "unknown")[:64],
        "exc_type": safe_exc_type,
        "safe_summary": safe_message,
        "version": PRODUCT_VERSION,
        "installation_id": get_installation_identity(touch=False).get("installation_id"),
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
    )
    return {"ok": ok, "crash_id": row["crash_id"]}


def list_crashes(*, data_dir: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_jsonl(_crashes_path(data_dir), limit=limit)
    rows.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return rows[:limit]


def _minimize_crash_item(row: Dict[str, Any]) -> Dict[str, Any]:
    """P1 admin data minimization: safe crash summary without raw messages."""
    return {
        "crash_id": row.get("crash_id") or "",
        "at": row.get("at") or "",
        "kind": row.get("kind") or "unknown",
        "exc_type": row.get("exc_type") or "",
        "version": row.get("version") or "",
        # safe_summary is already redacted at write time (P0-2)
        "message": str(row.get("safe_summary") or row.get("message") or "")[:160],
    }


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
        # P1: minimized items — no raw messages, no context dicts.
        "recent": [_minimize_crash_item(r) for r in rows[:10]],
    }


# --------------------------------------------------------------------------
# Feedback inbox
# --------------------------------------------------------------------------

def list_feedback(*, data_dir: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    rows = _read_jsonl(_feedback_path(data_dir), limit=limit)
    rows.sort(key=lambda r: r.get("timestamp") or r.get("at") or "", reverse=True)
    return rows[:limit]


def list_feedback_minimized(*, data_dir: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Return minimized feedback items safe for admin display (P1 data minimization)."""
    return [_minimize_feedback_item(r) for r in list_feedback(data_dir=data_dir, limit=limit)]


def _minimize_feedback_item(row: Dict[str, Any]) -> Dict[str, Any]:
    """P1 admin data minimization: return only safe display fields, no raw paths or email."""
    return {
        "feedback_id": row.get("feedback_id") or "",
        "category": row.get("category") or "general",
        "timestamp": row.get("timestamp") or row.get("at") or "",
        "version": row.get("version") or "",
        "page": row.get("page") or "",
        "summary": str(row.get("message") or "")[:120],
    }


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
        # P1: minimized items — no raw messages, no email, no paths.
        "items": [_minimize_feedback_item(r) for r in rows[:20]],
    }


# --------------------------------------------------------------------------
# Phase 189 — result feedback funnel inbox
# --------------------------------------------------------------------------

def _redact_comment(text: str) -> str:
    """Defense-in-depth: re-redact a comment at read time (already redacted on write)."""
    if not text:
        return ""
    try:
        from .install_support import _redact_support_text

        return _redact_support_text(text)
    except Exception:
        return text


def _minimize_result_feedback_item(row: Dict[str, Any]) -> Dict[str, Any]:
    """Safe operator view of a result-feedback row.

    Exposes workflow, useful, category, redacted comment, user email (for
    follow-up), and timestamp. Never exposes tokens, hashes, paths, or source.
    """
    return {
        "feedback_id": row.get("feedback_id") or "",
        "workflow": str(row.get("workflow") or "")[:32],
        "useful": bool(row.get("useful")),
        "category": str(row.get("category") or "general")[:48],
        "comment": _redact_comment(str(row.get("comment") or row.get("message") or ""))[:400],
        "email": str(row.get("email") or "")[:200],
        "timestamp": row.get("timestamp") or row.get("at") or "",
        "version": str(row.get("version") or "")[:32],
        "repo_metadata": row.get("repo_metadata") or {},
    }


def list_result_feedback(*, data_dir: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    rows = [r for r in list_feedback(data_dir=data_dir, limit=500) if r.get("kind") == "result_feedback"]
    return rows[:limit]


def result_feedback_inbox(*, data_dir: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    rows = list_result_feedback(data_dir=data_dir, limit=limit)
    by_workflow: Dict[str, int] = {}
    useful_yes = 0
    useful_no = 0
    for row in rows:
        wf = str(row.get("workflow") or "unknown")
        by_workflow[wf] = by_workflow.get(wf, 0) + 1
        if row.get("useful"):
            useful_yes += 1
        else:
            useful_no += 1
    return {
        "total": len(rows),
        "by_workflow": by_workflow,
        "useful_yes": useful_yes,
        "useful_no": useful_no,
        "items": [_minimize_result_feedback_item(r) for r in rows],
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
