"""Atlas Accounts route handlers for server.py's _route_handlers()."""
from __future__ import annotations

import platform
import re
from typing import Any, Dict

from . import accounts_client
from . import accounts_service_runner


def _app_version() -> str:
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


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PROFILE_REQUIRED_FIELDS = (
    "currently_developer",
    "project_use",
    "company_size",
    "developer_experience",
    "primary_role",
    "coding_tools",
    "repo_size",
    "atlas_help",
)


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.match(email or ""))


def _validate_beta_profile(profile: Dict[str, Any]) -> str:
    if not isinstance(profile, dict):
        return "Complete the beta profile before creating your account."
    for field in _PROFILE_REQUIRED_FIELDS:
        value = profile.get(field)
        if value is None or value == "" or value == []:
            return "Complete the required beta profile fields."
    if not isinstance(profile.get("currently_developer"), bool):
        return "Choose whether you currently work as a developer."
    for list_field in ("coding_tools", "atlas_help"):
        value = profile.get(list_field)
        if not isinstance(value, list) or not value:
            return "Select at least one option in each beta profile checklist."
    return ""


def _service_unavailable_response() -> Dict[str, Any]:
    return {
        "ok": False,
        "code": "service_unavailable",
        "submitted": False,
        "error": "We could not reach the Atlas account service.",
        "detail": "Your application has not been submitted yet.",
    }


def accounts_state(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return accounts_client.get_account_state()


def accounts_register(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    confirm = str(body.get("confirm_password", ""))
    if not email or not password:
        return {"ok": False, "code": "validation_error", "submitted": False, "error": "Email and password are required."}
    if not _valid_email(email):
        return {"ok": False, "code": "validation_error", "submitted": False, "error": "Enter a valid email address."}
    if password != confirm:
        return {"ok": False, "code": "validation_error", "submitted": False, "error": "Passwords do not match."}
    profile_error = _validate_beta_profile(body.get("beta_profile") or {})
    if profile_error:
        return {"ok": False, "code": "validation_error", "submitted": False, "error": profile_error}

    if not accounts_service_runner.ensure_running():
        return _service_unavailable_response()

    result = accounts_client.register(
        email=email,
        password=password,
        app_version=_app_version(),
        platform=_platform_str(),
        beta_profile=body.get("beta_profile") or {},
    )
    if result.get("_offline"):
        return _service_unavailable_response()
    if result.get("_http_status"):
        status = int(result.get("_http_status") or 0)
        detail = result.get("detail", "Registration failed")
        detail_text = detail if isinstance(detail, str) else str(detail)
        if status == 409:
            return {
                "ok": False,
                "code": "duplicate_email",
                "submitted": False,
                "account_created": True,
                "error": "An account with this email already exists.",
                "detail": "Your application may already be on file. Try signing in instead.",
            }
        return {"ok": False, "code": "registration_failed", "submitted": False, "error": detail_text}
    return {"ok": True, "submitted": True, **result}


def accounts_login(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        return {"ok": False, "error": "email and password are required"}
    if not _valid_email(email):
        return {"ok": False, "error": "Enter a valid email address."}
    if not accounts_service_runner.ensure_running():
        return {
            "ok": False,
            "code": "service_unavailable",
            "error": "The Atlas accounts service isn't available right now. Please restart Atlas, and contact support@useatlas.dev if this keeps happening.",
        }
    result = accounts_client.login(
        email=email,
        password=password,
        app_version=_app_version(),
        platform=_platform_str(),
    )
    if result.get("_offline"):
        return {
            "ok": False,
            "code": "service_unavailable",
            "error": "The Atlas accounts service isn't available right now. Please restart Atlas, and contact support@useatlas.dev if this keeps happening.",
        }
    if result.get("_http_status"):
        detail = result.get("detail", "Login failed")
        return {"ok": False, "error": detail if isinstance(detail, str) else str(detail)}
    return {"ok": True, **result}


def accounts_logout(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    accounts_client.logout()
    return {"ok": True}


def accounts_profile(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_profile()
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Not signed in"}
    return {"ok": True, "user": result}


def accounts_license(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return {"ok": True, **accounts_client.get_license_status()}


def accounts_devices(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_devices()
    if isinstance(result, list):
        return {"ok": True, "devices": result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Not signed in"}
    return {"ok": True, "devices": result}


def accounts_remove_device(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
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


def accounts_admin_users(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_admin_users()
    if isinstance(result, list):
        return {"ok": True, "users": result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Admin access required.")}
    return {"ok": True, "users": result if isinstance(result, list) else []}


def accounts_admin_pending(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_admin_pending_applications()
    if isinstance(result, list):
        return {"ok": True, "applications": result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Admin access required.")}
    return {"ok": True, "applications": []}


def accounts_admin_notifications(_body: Dict[str, Any], query: Dict[str, str]) -> Dict[str, Any]:
    unread_only = query.get("unread_only", "1") not in ("0", "false", "False")
    result = accounts_client.get_admin_notifications(unread_only=unread_only)
    if isinstance(result, list):
        return {"ok": True, "notifications": result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Admin access required.")}
    return {"ok": True, "notifications": []}


def accounts_admin_approve(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    result = accounts_client.approve_application(uid, body.get("admin_notes"))
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Approval failed.")}
    return {"ok": True, "user": result}


def accounts_admin_reject(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    result = accounts_client.reject_application(uid, body.get("admin_notes"))
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Rejection failed.")}
    return {"ok": True, "user": result}


def accounts_service_status(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    running = accounts_client.is_service_running()
    if not running:
        running = accounts_service_runner.ensure_running(timeout=8.0)
    return {"running": running}


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
    ("GET",  "/api/accounts/admin/users"):     accounts_admin_users,
    ("GET",  "/api/accounts/admin/applications/pending"): accounts_admin_pending,
    ("GET",  "/api/accounts/admin/notifications"): accounts_admin_notifications,
    ("POST", "/api/accounts/admin/applications/approve"): accounts_admin_approve,
    ("POST", "/api/accounts/admin/applications/reject"): accounts_admin_reject,
}
