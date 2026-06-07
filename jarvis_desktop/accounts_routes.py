"""Atlas Accounts route handlers for server.py's _route_handlers().

Adds /api/accounts/* endpoints so the desktop frontend can call the
accounts service through the local server (avoids CORS issues and
keeps all API calls to the same origin for the JS layer).
"""
from __future__ import annotations

import platform
from typing import Any, Dict

from . import accounts_client


def _app_version() -> str:
    """Read app version from build_info or fallback."""
    try:
        import os, json
        here = os.path.dirname(__file__)
        info_path = os.path.join(here, "build_info.json")
        with open(info_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("version", "0.1.0-beta")
    except Exception:
        return "0.1.0-beta"


def _platform_str() -> str:
    return f"{platform.system()} {platform.release()}"


# ── Route handlers ─────────────────────────────────────────────────────────────

def accounts_state(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """GET /api/accounts/state — combined auth + license + device state."""
    return accounts_client.get_account_state()


def accounts_register(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """POST /api/accounts/register"""
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        return {"ok": False, "error": "email and password are required"}
    result = accounts_client.register(
        email=email,
        password=password,
        app_version=_app_version(),
        platform=_platform_str(),
    )
    if result.get("_offline"):
        return {"ok": False, "error": "Accounts service is not running. Start it with: python -m accounts_service.main"}
    if result.get("_http_status"):
        detail = result.get("detail", "Registration failed")
        return {"ok": False, "error": detail if isinstance(detail, str) else str(detail)}
    return {"ok": True, **result}


def accounts_login(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """POST /api/accounts/login"""
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        return {"ok": False, "error": "email and password are required"}
    result = accounts_client.login(
        email=email,
        password=password,
        app_version=_app_version(),
        platform=_platform_str(),
    )
    if result.get("_offline"):
        return {"ok": False, "error": "Accounts service is not running."}
    if result.get("_http_status"):
        detail = result.get("detail", "Login failed")
        return {"ok": False, "error": detail if isinstance(detail, str) else str(detail)}
    return {"ok": True, **result}


def accounts_logout(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """POST /api/accounts/logout"""
    accounts_client.logout()
    return {"ok": True}


def accounts_profile(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """GET /api/accounts/profile"""
    result = accounts_client.get_profile()
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Not signed in"}
    return {"ok": True, "user": result}


def accounts_license(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """GET /api/accounts/license"""
    return {"ok": True, **accounts_client.get_license_status()}


def accounts_devices(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """GET /api/accounts/devices"""
    result = accounts_client.get_devices()
    if isinstance(result, list):
        return {"ok": True, "devices": result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Not signed in"}
    return {"ok": True, "devices": result}


def accounts_remove_device(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """POST /api/accounts/devices/remove"""
    device_id = str(body.get("device_id", "")).strip()
    if not device_id:
        return {"ok": False, "error": "device_id required"}
    result = accounts_client.remove_device(device_id)
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Not signed in"}
    if result.get("_http_status", 0) == 204 or result == {}:
        return {"ok": True}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Failed to remove device")}
    return {"ok": True}


def accounts_service_status(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    """GET /api/accounts/service-status"""
    return {"running": accounts_client.is_service_running()}


# ── Route table — merge into server._route_handlers() ──────────────────────
ACCOUNTS_ROUTES = {
    ("GET",  "/api/accounts/state"):          accounts_state,
    ("POST", "/api/accounts/register"):       accounts_register,
    ("POST", "/api/accounts/login"):          accounts_login,
    ("POST", "/api/accounts/logout"):         accounts_logout,
    ("GET",  "/api/accounts/profile"):        accounts_profile,
    ("GET",  "/api/accounts/license"):        accounts_license,
    ("GET",  "/api/accounts/devices"):        accounts_devices,
    ("POST", "/api/accounts/devices/remove"): accounts_remove_device,
    ("GET",  "/api/accounts/service-status"): accounts_service_status,
}
