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

# ── File helpers ──────────────────────────────────────────────────────────────

def _state_path() -> str:
    return os.path.join(desktop_data_dir(), "accounts_state.json")


def _load_state() -> Dict[str, Any]:
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
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

def _token_payload(token: str) -> Dict[str, Any]:
    """Decode JWT payload (no signature check — service already validated)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        import base64
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return {}


def _is_access_token_valid(access_token: str) -> bool:
    payload = _token_payload(access_token)
    exp = payload.get("exp", 0)
    return time.time() < (exp - _ACCESS_TOKEN_BUFFER_SECONDS)


def get_valid_access_token() -> Optional[str]:
    """Return a valid access token, refreshing automatically if needed."""
    state = _load_state()
    access_token = state.get("access_token")
    refresh_token = state.get("refresh_token")

    if access_token and _is_access_token_valid(access_token):
        return access_token

    if not refresh_token:
        return None

    # Attempt token refresh
    result = _call("POST", "/auth/refresh", {
        "refresh_token": refresh_token,
        "device_id": get_device_id(),
    })
    if result.get("_offline") or result.get("_http_status"):
        # Offline or error — return stale access token if we have one (offline grace)
        return access_token or None

    _persist_token_response(result, state)
    return state.get("access_token")


def _persist_token_response(result: Dict[str, Any], state: Optional[Dict] = None) -> None:
    """Extract tokens from a TokenResponse and save to state."""
    if state is None:
        state = _load_state()
    if "access_token" in result:
        state["access_token"] = result["access_token"]
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
    token = get_valid_access_token()

    # Online: refresh from server
    if token:
        result = _call("GET", "/user/license", access_token=token)
        if not result.get("_offline") and not result.get("_http_status"):
            state["license"] = result
            state["license_checked_at"] = time.time()
            _save_state(state)
            return result

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
    state.pop("access_token", None)
    state.pop("refresh_token", None)
    state.pop("user", None)
    state.pop("license", None)
    state.pop("license_checked_at", None)
    _save_state(state)


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
    state = _load_state()
    token = get_valid_access_token()
    license_status = get_license_status()
    user = state.get("user")

    return {
        "authenticated": bool(token and user),
        "user": user,
        "license": license_status,
        "device_id": get_device_id(),
        "service_online": bool(token and not license_status.get("_offline")),
    }
