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
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .data_paths import desktop_data_dir

# ── Configuration ─────────────────────────────────────────────────────────────
_SERVICE_BASE = os.environ.get("ATLAS_ACCOUNTS_URL", "http://127.0.0.1:8788")
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

def _call(
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Make an HTTP request to the accounts service. Returns parsed JSON."""
    url = f"{_SERVICE_BASE}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers: Dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_CONNECT_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        try:
            err = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            err = {"detail": body or str(exc)}
        err["_http_status"] = exc.code
        return err
    except (urllib.error.URLError, OSError):
        return {"_offline": True, "detail": "accounts service unreachable"}


# ── Token management ──────────────────────────────────────────────────────────

def _extract_access_token_exp(access_token: str) -> Optional[float]:
    """Read exp from a freshly issued access token (server response only)."""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return None
        import base64
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
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


def get_valid_access_token() -> Optional[str]:
    """Return a valid access token, refreshing automatically if needed."""
    state = _load_state()
    if state.get("_state_integrity_error"):
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
            _clear_auth_state(state, "auth_rejected")
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
    token = get_valid_access_token()

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
            if status_code in (401, 403):
                _clear_auth_state(state, "account_unavailable")
            return {
                "valid": False,
                "plan": "free",
                "status": "account_unavailable" if status_code in (401, 403) else "license_check_failed",
                "_http_status": status_code,
                "message": "Atlas account is not available. Please sign in again.",
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
    """Quick check if the accounts service is reachable."""
    result = _call("GET", "/health")
    return result.get("status") == "ok"


def register(email: str, password: str, app_version: str, platform: str) -> Dict[str, Any]:
    """Register a new account."""
    result = _call("POST", "/auth/register", {
        "email": email,
        "password": password,
        "device_id": get_device_id(),
        "app_version": app_version,
        "platform": platform,
    })
    if "access_token" in result:
        _persist_token_response(result)
    return result


def login(email: str, password: str, app_version: str, platform: str) -> Dict[str, Any]:
    """Authenticate and cache tokens."""
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
    """Revoke refresh token and clear local state."""
    state = _load_state()
    refresh_token = state.get("refresh_token")
    if refresh_token:
        _call("POST", "/auth/logout", {"refresh_token": refresh_token})
    # Clear credentials regardless of server response
    _clear_auth_state(state)


def get_profile() -> Dict[str, Any]:
    """Return cached user profile, falling back to server if stale."""
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

    return {
        "authenticated": authenticated,
        "user": user,
        "license": license_status,
        "device_id": get_device_id(),
        "service_online": bool(token and not license_status.get("_offline") and not license_status.get("_http_status")),
        "state_integrity_error": bool(state.get("_state_integrity_error")),
    }
