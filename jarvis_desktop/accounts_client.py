"""Atlas Accounts Client — stdlib-only desktop client for the accounts service.

Uses only Python standard library so no pip dependencies are added to the
desktop application. Communicates with the Atlas Accounts Service over HTTP.

Responsibilities:
  - Persistent device_id (generated once, stored in data dir)
  - Token cache (access + refresh tokens, stored in accounts_state.json)
  - License cache with offline grace (7 days after last successful check)
  - All account API calls proxied through this module
  - Privacy: NEVER includes source code, file paths, or prompt text in payloads
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .data_paths import desktop_data_dir

# ── Configuration ─────────────────────────────────────────────────────────────
# Local accounts service (dev-only fallback).
_SERVICE_BASE = os.environ.get("ATLAS_ACCOUNTS_URL", "http://127.0.0.1:8788")


def web_base() -> str:
    """Base URL of the website auth authority (Supabase-backed)."""
    return (os.environ.get("ATLAS_WEB_URL") or "https://atlas-repo-wu76.vercel.app").rstrip("/")


def auth_mode() -> str:
    """Which identity authority to use (Phase 186A).

    "website" → the desktop authenticates against the website /api/auth/desktop/*
    endpoints (Supabase-backed; single source of truth). No local accounts service.
    "local"   → the legacy local FastAPI accounts service (dev fallback only).

    Default: the PACKAGED app (frozen exe) uses the website authority so it never
    depends on a bundled local service. Source/dev (and the test suite, which runs
    unfrozen) default to local to preserve existing behavior. Override explicitly
    with ATLAS_AUTH_MODE=website|local (or ATLAS_DEV=1 / ATLAS_LOCAL_ACCOUNTS=1).
    """
    m = (os.environ.get("ATLAS_AUTH_MODE") or "").strip().lower()
    if m in ("website", "local"):
        return m
    if os.environ.get("ATLAS_LOCAL_ACCOUNTS") == "1" or os.environ.get("ATLAS_DEV") == "1":
        return "local"
    return "website" if getattr(sys, "frozen", False) else "local"
_OFFLINE_GRACE_SECONDS = 7 * 24 * 3600   # 7 days
_ACCESS_TOKEN_BUFFER_SECONDS = 120        # refresh if <2 min left
_CONNECT_TIMEOUT = 5                      # seconds
_INTEGRITY_FIELD = "_integrity"
_STATE_SECRET_FILE = "accounts_state_secret"
_SIGNED_STATE_KEYS = (
    "device_id",
    "access_token",
    "access_token_expires_at",
    "refresh_token",
    "user",
    "license",
    "license_checked_at",
)
_SENSITIVE_STATE_KEYS = {
    "access_token",
    "access_token_expires_at",
    "refresh_token",
    "user",
    "license",
    "license_checked_at",
}

# ── File helpers ──────────────────────────────────────────────────────────────

def _state_path() -> str:
    return os.path.join(desktop_data_dir(), "accounts_state.json")


def _state_secret_path() -> str:
    return os.path.join(desktop_data_dir(), _STATE_SECRET_FILE)


def _load_state_secret() -> str:
    path = _state_secret_path()
    try:
        with open(path, encoding="utf-8") as f:
            secret = f.read().strip()
        if secret:
            return secret
    except OSError:
        pass
    secret = secrets.token_hex(32)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(secret)
    except OSError:
        pass
    return secret


def _state_payload(state: Dict[str, Any]) -> bytes:
    signed = {key: state.get(key) for key in _SIGNED_STATE_KEYS if key in state}
    return json.dumps(signed, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _state_digest(state: Dict[str, Any]) -> str:
    return hmac.new(_load_state_secret().encode("utf-8"), _state_payload(state), hashlib.sha256).hexdigest()


def _has_sensitive_state(state: Dict[str, Any]) -> bool:
    return any(key in state for key in _SENSITIVE_STATE_KEYS)


def _state_integrity_valid(state: Dict[str, Any]) -> bool:
    meta = state.get(_INTEGRITY_FIELD)
    if not isinstance(meta, dict):
        return False
    expected = str(meta.get("sha256", ""))
    if not expected:
        return False
    unsigned = {key: value for key, value in state.items() if key != _INTEGRITY_FIELD}
    return hmac.compare_digest(expected, _state_digest(unsigned))


def _load_state() -> Dict[str, Any]:
    try:
        with open(_state_path(), encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(state, dict):
        return {}
    if _has_sensitive_state(state) and not _state_integrity_valid(state):
        clean: Dict[str, Any] = {"_state_integrity_error": True}
        if isinstance(state.get("device_id"), str):
            clean["device_id"] = state["device_id"]
        return clean
    return state


def _save_state(state: Dict[str, Any]) -> None:
    state = {key: value for key, value in state.items() if key != "_state_integrity_error"}
    unsigned = {key: value for key, value in state.items() if key != _INTEGRITY_FIELD}
    unsigned[_INTEGRITY_FIELD] = {"version": 1, "sha256": _state_digest(unsigned)}
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(unsigned, f, indent=2)
    except OSError:
        pass


def cached_identity() -> Dict[str, Any]:
    """Return the locally cached account identity (no network call).

    Used by feedback to attach user_id/email when authenticated. Reads only the
    signed local state file; never triggers a license refresh or network call.
    Returns safe fields only — never tokens or hashes.
    """
    state = _load_state()
    if state.get("_state_integrity_error"):
        return {"authenticated": False, "user_id": "", "email": ""}
    user = state.get("user") if isinstance(state.get("user"), dict) else {}
    has_token = bool(state.get("access_token"))
    return {
        "authenticated": bool(has_token and user),
        "user_id": str(user.get("user_id") or "")[:64],
        "email": str(user.get("email") or "")[:200],
    }


def get_device_id() -> str:
    """Return this device's persistent ID, creating it if necessary."""
    state = _load_state()
    if state.get("device_id"):
        return state["device_id"]
    # Generate a new random device ID
    device_id = secrets.token_hex(16)
    state["device_id"] = device_id
    _save_state(state)
    return device_id


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _looks_json(content_type: str, body: str) -> bool:
    """True if the response is (or claims to be) JSON."""
    if "json" in (content_type or "").lower():
        return True
    stripped = (body or "").lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _non_json_error(url: str, status: int) -> Dict[str, Any]:
    """Clean error for a non-JSON response (e.g. an HTML 404 page from a wrong
    route/deployment). We NEVER surface the raw HTML body to the UI — it would
    dump a whole error page into the login box. The message names the URL so the
    cause (missing API route / wrong deployment) is obvious."""
    msg = (
        f"Atlas server returned a non-JSON response from {url}. "
        "This usually means the desktop is calling a missing API route or the wrong deployment."
    )
    return {"ok": False, "_non_json": True, "_http_status": status, "error": msg, "detail": msg}


def _call(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    access_token: Optional[str] = None,
    base: Optional[str] = None,
) -> Dict[str, Any]:
    """Make an HTTP request to an accounts backend. Returns parsed JSON.

    `base` selects the backend; defaults to the local service. Website-auth calls
    pass base=web_base(). Non-JSON responses are converted to a clean error dict
    (the raw body is never returned) so the desktop UI can't render an HTML page.
    """
    url = f"{base or _SERVICE_BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT) as resp:
            ctype = resp.headers.get("Content-Type", "") if resp.headers else ""
            body = resp.read().decode("utf-8", errors="replace")
            if not body:
                return {}
            if not _looks_json(ctype, body):
                return _non_json_error(url, getattr(resp, "status", 200) or 200)
            try:
                return json.loads(body)
            except (json.JSONDecodeError, ValueError):
                return _non_json_error(url, getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        if body and _looks_json(ctype, body):
            try:
                err = json.loads(body)
                err["_http_status"] = exc.code
                return err
            except (json.JSONDecodeError, ValueError):
                pass
        err = _non_json_error(url, exc.code)
        err["_http_status"] = exc.code
        return err
    except (urllib.error.URLError, OSError):
        return {"_offline": True, "detail": "Atlas account service is unreachable. Check your connection and try again."}


# ── Token management ──────────────────────────────────────────────────────────

def _extract_access_token_exp(access_token: str) -> Optional[float]:
    """Read exp from a freshly issued access token (server response only)."""
    try:
        parts = access_token.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1]   # JWT header.payload.sig (local accounts service)
        elif len(parts) == 2:
            payload_b64 = parts[0]   # Atlas web token: base64url(payload).hmac
        else:
            return None
        import base64
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        exp = payload.get("exp")
        return float(exp) if exp is not None else None
    except Exception:
        return None


def _is_access_token_valid(access_token: str, state: Dict[str, Any]) -> bool:
    exp = state.get("access_token_expires_at")
    if exp is None:
        return False
    try:
        return time.time() < (float(exp) - _ACCESS_TOKEN_BUFFER_SECONDS)
    except (TypeError, ValueError):
        return False


def _clear_auth_state(state: Optional[Dict[str, Any]] = None, reason: str = "") -> None:
    if state is None:
        state = _load_state()
    for key in (
        "access_token",
        "refresh_token",
        "access_token_expires_at",
        "user",
        "license",
        "license_checked_at",
    ):
        state.pop(key, None)
    if reason:
        state["last_auth_error"] = reason
    _save_state(state)


def _error_status(result: Dict[str, Any], default: str = "account_unavailable") -> str:
    detail = str(result.get("detail") or result.get("error") or result.get("message") or "").lower()
    if "device" in detail and "revoked" in detail:
        return "device_revoked"
    if "suspended" in detail:
        return "suspended"
    if "banned" in detail:
        return "banned"
    if "expired" in detail:
        return "expired"
    if "past due" in detail or "past_due" in detail:
        return "past_due"
    if "canceled" in detail or "cancelled" in detail:
        return "canceled"
    return default


def _status_message(status: str) -> str:
    return {
        "device_revoked": "This device is no longer authorized for this account.",
        "suspended": "This account is suspended. Contact support.",
        "banned": "This account is banned and cannot access Atlas.",
        "expired": "Your Atlas access is not currently active.",
        "past_due": "Your Atlas subscription is past due. Update billing to continue.",
        "canceled": "Your Atlas subscription is canceled. Reactivate billing to continue.",
        "cancelled": "Your Atlas subscription is cancelled. Reactivate billing to continue.",
        "trial_missing_expiry": "Your Atlas trial is missing an expiry date. Contact support.",
        "account_unavailable": "Your Atlas access is not currently active.",
    }.get(status, "Atlas account is not available. Please sign in again.")


def get_valid_access_token() -> Optional[str]:
    """Return a valid access token, refreshing automatically if needed."""
    state = _load_state()
    if state.get("_state_integrity_error"):
        return None
    if auth_mode() == "website":
        # Website tokens are self-contained and not refreshed; expiry → re-login.
        token = state.get("access_token")
        if token and _is_access_token_valid(token, state):
            return token
        if token:
            _clear_auth_state(state, "session_expired")
        return None
    access_token = state.get("access_token")
    refresh_token = state.get("refresh_token")

    if access_token and _is_access_token_valid(access_token, state):
        return access_token

    if not refresh_token:
        return None

    # Attempt token refresh
    result = _call("POST", "/auth/refresh", {
        "refresh_token": refresh_token,
        "device_id": get_device_id(),
    })
    if result.get("_offline"):
        return access_token or None
    if result.get("_http_status"):
        if int(result.get("_http_status") or 0) in (401, 403):
            _clear_auth_state(state, _error_status(result, "auth_rejected"))
        return None

    _persist_token_response(result, state)
    return state.get("access_token")


def _persist_token_response(result: Dict[str, Any], state: Optional[Dict] = None) -> None:
    """Extract tokens from a TokenResponse and save to state."""
    if state is None:
        state = _load_state()
    if "access_token" in result:
        state["access_token"] = result["access_token"]
        exp = _extract_access_token_exp(result["access_token"])
        if exp is not None:
            state["access_token_expires_at"] = exp
        else:
            state.pop("access_token_expires_at", None)
    if "refresh_token" in result:
        state["refresh_token"] = result["refresh_token"]
    if "user" in result and result["user"]:
        state["user"] = result["user"]
    if "license" in result and result["license"]:
        state["license"] = result["license"]
        state["license_checked_at"] = time.time()
    _save_state(state)


# ── Website auth (Phase 186A) ───────────────────────────────────────────────────

def _web_user_normalize(user: Any) -> Dict[str, Any]:
    """Website users key on `id`; keep `user_id` populated for compatibility with
    cached_identity() and the desktop UI."""
    if not isinstance(user, dict):
        return {}
    u = dict(user)
    if not u.get("user_id") and u.get("id"):
        u["user_id"] = u["id"]
    return u


def _web_license_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Map a website /me|login response to the desktop license shape.
    Normal accounts are active immediately; only suspended accounts are blocked."""
    user = result.get("user") or {}
    plan = result.get("plan") or "free"
    plan_status = result.get("planStatus") or "none"
    if user.get("status") == "suspended":
        return {"valid": False, "plan": plan, "status": "suspended",
                "message": "This account is suspended. Contact support."}
    return {"valid": True, "plan": plan, "plan_status": plan_status, "status": "active",
            "message": "Account active."}


def _persist_web_session(result: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> None:
    if state is None:
        state = _load_state()
    token = result.get("token")
    if token:
        state["access_token"] = token
        exp = _extract_access_token_exp(token)
        if exp is not None:
            state["access_token_expires_at"] = exp
        else:
            state.pop("access_token_expires_at", None)
    state.pop("refresh_token", None)  # website tokens are not refreshed — re-login on expiry
    if result.get("user"):
        state["user"] = _web_user_normalize(result["user"])
    state["license"] = _web_license_from_result(result)
    state["license_checked_at"] = time.time()
    state.pop("last_auth_error", None)
    _save_state(state)


def _web_login(email: str, password: str) -> Dict[str, Any]:
    result = _call("POST", "/api/auth/desktop/login", {"email": email, "password": password}, base=web_base())
    if result.get("ok") and result.get("token"):
        _persist_web_session(result)
    elif not result.get("_offline"):
        result.setdefault("detail", result.get("error") or "Login failed.")
    return result


def _web_register(email: str, password: str, name: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"email": email, "password": password}
    if name:
        payload["name"] = name
    result = _call("POST", "/api/auth/desktop/register", payload, base=web_base())
    if result.get("ok") and result.get("token"):
        _persist_web_session(result)
    elif not result.get("_offline"):
        result.setdefault("detail", result.get("error") or "Registration failed.")
    return result


def _web_license_status() -> Dict[str, Any]:
    token = get_valid_access_token()
    state = _load_state()
    if token:
        result = _call("GET", "/api/auth/desktop/me", access_token=token, base=web_base())
        if result.get("ok") and not result.get("_offline") and not result.get("_http_status"):
            lic = _web_license_from_result(result)
            state["user"] = _web_user_normalize(result.get("user") or state.get("user") or {})
            state["license"] = lic
            state["license_checked_at"] = time.time()
            _save_state(state)
            return lic
        if result.get("_http_status") and int(result.get("_http_status") or 0) in (401, 403):
            _clear_auth_state(state, "account_unavailable")
            return {"valid": False, "plan": "free", "status": "account_unavailable",
                    "message": _status_message("account_unavailable")}
    # Offline grace — reuse the cached license within the 7-day window.
    cached = state.get("license")
    checked_at = state.get("license_checked_at", 0)
    elapsed = time.time() - checked_at
    if cached and elapsed < _OFFLINE_GRACE_SECONDS:
        cached = dict(cached)
        cached["_offline"] = True
        cached["_offline_grace_remaining_hours"] = round((_OFFLINE_GRACE_SECONDS - elapsed) / 3600, 1)
        return cached
    if cached and elapsed >= _OFFLINE_GRACE_SECONDS:
        return {"valid": False, "plan": "free", "status": "offline_grace_expired", "_offline": True,
                "message": "Atlas is offline and the 7-day grace period has expired. Please reconnect to continue."}
    return {"valid": False, "plan": "free", "status": "unauthenticated", "_offline": not token,
            "message": "Sign in to activate Atlas."}


def verify_session() -> Dict[str, Any]:
    """Startup session check (Phase 186A). Validates the cached token against the
    authority (/me in website mode) and clears local state on rejection."""
    state = _load_state()
    if not state.get("access_token"):
        return {"authenticated": False, "reason": "no_token"}
    lic = get_license_status()
    state = _load_state()
    signed_in = bool(state.get("access_token") and state.get("user"))
    return {
        "authenticated": bool(signed_in and lic.get("valid") is True),
        "signed_in": signed_in,
        "user": state.get("user"),
        "license": lic,
    }


# ── License / offline grace ────────────────────────────────────────────────────

def get_license_status() -> Dict[str, Any]:
    """Return license status with offline grace fallback."""
    state = _load_state()
    if state.get("_state_integrity_error"):
        return {
            "valid": False,
            "plan": "free",
            "status": "local_state_tampered",
            "_offline": False,
            "message": "Atlas account cache integrity failed. Please sign in again.",
        }
    if auth_mode() == "website":
        return _web_license_status()
    token = get_valid_access_token()
    state = _load_state()

    # Online: refresh from server
    if token:
        result = _call("GET", "/user/license", access_token=token)
        if not result.get("_offline") and not result.get("_http_status"):
            state["license"] = result
            state["license_checked_at"] = time.time()
            _save_state(state)
            return result
        if result.get("_http_status"):
            status_code = int(result.get("_http_status") or 0)
            status_label = _error_status(result)
            if status_code in (401, 403):
                _clear_auth_state(state, status_label)
            return {
                "valid": False,
                "plan": "free",
                "status": status_label if status_code in (401, 403) else "license_check_failed",
                "_http_status": status_code,
                "message": _status_message(status_label),
            }

    last_error = state.get("last_auth_error")
    if last_error in {
        "device_revoked",
        "suspended",
        "banned",
        "expired",
        "past_due",
        "canceled",
        "cancelled",
        "trial_missing_expiry",
        "account_unavailable",
    }:
        return {
            "valid": False,
            "plan": "free",
            "status": last_error,
            "_offline": False,
            "message": _status_message(last_error),
        }

    # Offline path — check grace window
    cached = state.get("license")
    checked_at = state.get("license_checked_at", 0)
    elapsed = time.time() - checked_at

    if cached and elapsed < _OFFLINE_GRACE_SECONDS:
        cached["_offline"] = True
        cached["_offline_grace_remaining_hours"] = round((_OFFLINE_GRACE_SECONDS - elapsed) / 3600, 1)
        return cached

    if cached and elapsed >= _OFFLINE_GRACE_SECONDS:
        # Grace period expired
        return {
            "valid": False,
            "plan": "free",
            "status": "offline_grace_expired",
            "_offline": True,
            "message": "Atlas is offline and the 7-day grace period has expired. Please reconnect to continue.",
        }

    # Never successfully checked (new install, never logged in)
    return {
        "valid": False,
        "plan": "free",
        "status": "unauthenticated",
        "_offline": not token,
        "message": "Sign in to activate Atlas.",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def is_service_running() -> bool:
    """Quick check if the accounts backend is reachable."""
    if auth_mode() == "website":
        # The auth authority is the website; there is no local service to start.
        # Real reachability surfaces as errors on login/me calls.
        return True
    result = _call("GET", "/health")
    return result.get("status") == "ok"


def register(
    email: str,
    password: str,
    app_version: str,
    platform: str,
    beta_profile: Optional[Dict[str, Any]] = None,
    invite_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new account."""
    if auth_mode() == "website":
        # Website auth captures email/password only; local profile fields remain legacy-compatible.
        return _web_register(email, password)
    payload: Dict[str, Any] = {
        "email": email,
        "password": password,
        "device_id": get_device_id(),
        "app_version": app_version,
        "platform": platform,
    }
    if beta_profile is not None:
        payload["beta_profile"] = beta_profile
    if invite_code:
        payload["invite_code"] = invite_code.strip()
    result = _call("POST", "/auth/register", payload)
    if "access_token" in result:
        _persist_token_response(result)
    return result


def login(email: str, password: str, app_version: str, platform: str) -> Dict[str, Any]:
    """Authenticate and cache tokens."""
    if auth_mode() == "website":
        return _web_login(email, password)
    result = _call("POST", "/auth/login", {
        "email": email,
        "password": password,
        "device_id": get_device_id(),
        "app_version": app_version,
        "platform": platform,
    })
    if "access_token" in result:
        _persist_token_response(result)
    return result


def logout() -> None:
    """Revoke session (best-effort) and clear local state."""
    state = _load_state()
    if auth_mode() == "website":
        token = state.get("access_token")
        if token:
            _call("POST", "/api/auth/desktop/logout", {}, access_token=token, base=web_base())
        _clear_auth_state(state)
        cleaned = _load_state()
        if cleaned.pop("last_auth_error", None) is not None:
            _save_state(cleaned)
        return
    refresh_token = state.get("refresh_token")
    if refresh_token:
        _call("POST", "/auth/logout", {"refresh_token": refresh_token})
    # Clear credentials regardless of server response
    _clear_auth_state(state)


def get_profile() -> Dict[str, Any]:
    """Return cached user profile, falling back to server if stale."""
    if auth_mode() == "website":
        token = get_valid_access_token()
        if not token:
            return _load_state().get("user") or {"_unauthenticated": True}
        result = _call("GET", "/api/auth/desktop/me", access_token=token, base=web_base())
        if result.get("ok") and not result.get("_offline") and not result.get("_http_status"):
            user = _web_user_normalize(result.get("user") or {})
            state = _load_state()
            state["user"] = user
            _save_state(state)
            return user
        if result.get("_http_status") and int(result.get("_http_status") or 0) in (401, 403):
            _clear_auth_state(reason="account_unavailable")
            return {"_unauthenticated": True, "status": "account_unavailable"}
        return _load_state().get("user") or {"_unauthenticated": True}
    token = get_valid_access_token()
    if not token:
        state = _load_state()
        return state.get("user") or {"_unauthenticated": True}
    result = _call("GET", "/user/me", access_token=token)
    if not result.get("_offline") and not result.get("_http_status"):
        state = _load_state()
        state["user"] = result
        _save_state(state)
    elif result.get("_http_status") and int(result.get("_http_status") or 0) in (401, 403):
        _clear_auth_state(reason="account_unavailable")
        return {"_unauthenticated": True, "status": "account_unavailable", "_http_status": result.get("_http_status")}
    return result


def get_devices() -> Dict[str, Any]:
    """List devices for the authenticated user."""
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/user/devices", access_token=token)


def remove_device(device_id: str) -> Dict[str, Any]:
    """Remove a device (self-service)."""
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("DELETE", f"/user/devices/{device_id}", access_token=token)


def get_admin_users() -> Dict[str, Any]:
    """Return account users for admin review. Requires current account admin token."""
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/users?limit=200", access_token=token)


def get_admin_pending_applications() -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/applications/pending?limit=200", access_token=token)


def get_admin_notifications(unread_only: bool = True) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    flag = "1" if unread_only else "0"
    return _call("GET", f"/admin/notifications?unread_only={flag}&limit=50", access_token=token)


def approve_application(user_id: str, admin_notes: Optional[str] = None) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    payload: Dict[str, Any] = {}
    if admin_notes:
        payload["admin_notes"] = admin_notes
    return _call("POST", f"/admin/users/{user_id}/approve-application", payload, access_token=token)


def reject_application(user_id: str, admin_notes: Optional[str] = None) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    payload: Dict[str, Any] = {}
    if admin_notes:
        payload["admin_notes"] = admin_notes
    return _call("POST", f"/admin/users/{user_id}/reject-application", payload, access_token=token)


def get_admin_dashboard() -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/dashboard", access_token=token)


def get_admin_audit_log(limit: int = 100) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", f"/admin/audit-log?limit={int(limit)}", access_token=token)


def admin_grant_beta(user_id: str) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("POST", f"/admin/users/{user_id}/grant-beta", {}, access_token=token)


def admin_revoke_beta(user_id: str) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("POST", f"/admin/users/{user_id}/revoke-beta", {}, access_token=token)


def admin_force_logout(user_id: str) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("POST", f"/admin/users/{user_id}/force-logout", {}, access_token=token)


_ADMIN_UPDATE_FIELDS = {"status", "role", "beta_flag", "plan", "license_status", "max_devices", "expires_at", "admin_notes"}


def admin_update_user(user_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    """PATCH a user — only the whitelisted admin-editable fields are forwarded."""
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    payload = {k: v for k, v in (fields or {}).items() if k in _ADMIN_UPDATE_FIELDS and v is not None}
    return _call("PATCH", f"/admin/users/{user_id}", payload, access_token=token)


def send_analytics_event(event_type: str, app_version: str, **counters: int) -> None:
    """Send a privacy-safe usage event. Only integer counters are sent."""
    token = get_valid_access_token()
    if not token:
        return  # Not logged in — skip silently
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Privacy: only integer counters + whitelisted string fields
    payload: Dict[str, Any] = {
        "device_id": get_device_id(),
        "event_type": event_type,
        "app_version": app_version,
        "date": today,
        "launches": 0,
        "scans": 0,
        "change_plans": 0,
        "debug_runs": 0,
        "what_breaks_runs": 0,
        "exports": 0,
        "estimated_tokens_saved": 0,
    }
    for k, v in counters.items():
        if k in payload and isinstance(v, int):
            payload[k] = v
    _call("POST", "/analytics/event", payload, access_token=token)


def submit_accounts_feedback(
    category: str,
    message: str,
    *,
    contact_email: Optional[str] = None,
    nps_score: Optional[int] = None,
    useful: Optional[bool] = None,
    workflow: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit structured feedback to the accounts service when signed in."""
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    payload: Dict[str, Any] = {"category": category, "message": message}
    if contact_email:
        payload["contact_email"] = contact_email
    if nps_score is not None:
        payload["nps_score"] = int(nps_score)
    if useful is not None:
        payload["useful"] = bool(useful)
    if workflow:
        payload["workflow"] = workflow
    return _call("POST", "/feedback", payload, access_token=token)


def record_acquisition_event(stage: str, *, source: str = "desktop", metadata: Optional[Dict[str, Any]] = None) -> None:
    """Record a funnel stage on the accounts service (best-effort)."""
    token = get_valid_access_token()
    payload: Dict[str, Any] = {
        "stage": stage,
        "device_id": get_device_id(),
        "source": source,
    }
    if metadata:
        payload["metadata"] = metadata
    if token:
        _call("POST", "/acquisition/event", payload, access_token=token)
    else:
        _call("POST", "/acquisition/event", payload)


def validate_invite_code(code: str) -> Dict[str, Any]:
    return _call("POST", "/acquisition/validate-invite", {"code": code})


def get_launch_readiness() -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/launch-readiness", access_token=token)


def get_admin_feedback(*, status: Optional[str] = None, category: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    q = f"?limit={int(limit)}"
    if status:
        q += f"&status={status}"
    if category:
        q += f"&category={category}"
    return _call("GET", f"/admin/feedback{q}", access_token=token)


def patch_admin_feedback(feedback_id: str, status: str) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("PATCH", f"/admin/feedback/{feedback_id}", {"status": status}, access_token=token)


def create_invite_code(
    *,
    email: Optional[str] = None,
    max_uses: int = 1,
    expires_days: Optional[int] = 30,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    payload: Dict[str, Any] = {"max_uses": max_uses, "expires_days": expires_days}
    if email:
        payload["email"] = email
    if notes:
        payload["notes"] = notes
    return _call("POST", "/admin/invites", payload, access_token=token)


def list_invite_codes(limit: int = 50) -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", f"/admin/invites?limit={int(limit)}", access_token=token)


def export_beta_users_admin() -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/export/beta-users", access_token=token)


def get_interview_summary() -> Dict[str, Any]:
    token = get_valid_access_token()
    if not token:
        return {"_unauthenticated": True}
    return _call("GET", "/admin/interview-summary", access_token=token)


def get_account_state() -> Dict[str, Any]:
    """Return a combined state object for the frontend accounts screen."""
    license_status = get_license_status()
    state = _load_state()
    if state.get("_state_integrity_error"):
        license_status = {
            "valid": False,
            "plan": "free",
            "status": "local_state_tampered",
            "_offline": False,
            "message": "Atlas account cache integrity failed. Please sign in again.",
        }
    token = state.get("access_token")
    user = state.get("user")
    authenticated = bool(token and user and license_status.get("valid") is True)
    # A user can be signed in (valid session + cached profile) yet not have an
    # active license. Such users must reach an
    # in-app status dashboard rather than a pre-login access wall (Phase 193).
    signed_in = bool(token and user)

    return {
        "authenticated": authenticated,
        "signed_in": signed_in,
        "user": user,
        "license": license_status,
        "device_id": get_device_id(),
        "service_online": bool(token and not license_status.get("_offline") and not license_status.get("_http_status")),
        "state_integrity_error": bool(state.get("_state_integrity_error")),
        "last_auth_error": state.get("last_auth_error"),
    }
