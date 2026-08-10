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
        return data.get("version", "1.0.0")
    except Exception:
        return "1.0.0"


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
        return "Complete your profile before creating your account."
    for field in _PROFILE_REQUIRED_FIELDS:
        value = profile.get(field)
        if value is None or value == "" or value == []:
            return "Complete the required profile fields."
    if not isinstance(profile.get("currently_developer"), bool):
        return "Choose whether you currently work as a developer."
    for list_field in ("coding_tools", "atlas_help"):
        value = profile.get(list_field)
        if not isinstance(value, list) or not value:
            return "Select at least one option in each profile checklist."
    return ""


def _service_unavailable_response() -> Dict[str, Any]:
    return {
        "ok": False,
        "code": "service_unavailable",
        "submitted": False,
        "error": "Accounts are temporarily unavailable. Atlas works fully in local mode.",
        "detail": "Your application has not been submitted yet.",
    }


def _accounts_backend_ready() -> bool:
    """Prepare the legacy helper only when it is the selected authority.

    Packaged Atlas uses the website authority.  Starting (or waiting for) the
    local helper in that mode made an otherwise healthy website account flow
    fail before it made its first network request.
    """
    if accounts_client.auth_mode() == "website":
        return True
    return accounts_service_runner.ensure_running()


def accounts_state(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return accounts_client.get_account_state()


def accounts_guest_start(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.start_guest_session()
    # "Continue without an account" is the first funnel step after launch and
    # the only onboarding choice this build offers, so a drop-off here means
    # the user never got past the first screen.
    if result.get("ok"):
        try:
            from .api import track_analytics_event

            track_analytics_event("onboarding_local_mode_selected", surface="first_run")
        except Exception:
            pass
    return result


def accounts_guest_clear(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return accounts_client.clear_guest_session()


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
    # The website authority collects email/password only; the local profile
    # questionnaire applies to the local accounts service only.
    if accounts_client.auth_mode() != "website":
        profile_error = _validate_beta_profile(body.get("beta_profile") or {})
        if profile_error:
            return {"ok": False, "code": "validation_error", "submitted": False, "error": profile_error}

    if not _accounts_backend_ready():
        return _service_unavailable_response()

    result = accounts_client.register(
        email=email,
        password=password,
        app_version=_app_version(),
        platform=_platform_str(),
        beta_profile=body.get("beta_profile") or {},
        invite_code=str(body.get("invite_code") or "").strip() or None,
    )
    if result.get("_offline"):
        return _service_unavailable_response()
    if result.get("_http_status"):
        status = int(result.get("_http_status") or 0)
        detail = result.get("detail", "Registration failed")
        # Never surface a raw validation blob (pydantic error list) to the user.
        detail_text = detail if isinstance(detail, str) else "Please check the form fields and try again."
        if status == 409:
            return {
                "ok": False,
                "code": "duplicate_email",
                "submitted": False,
                "account_created": True,
                "error": "An account with this email already exists.",
                "detail": "Your account may already exist. Try signing in instead.",
            }
        if status >= 500:
            # A backend fault is not the user's registration mistake — surface
            # it as a retryable outage, never as "registration failed".
            return _service_unavailable_response()
        return {"ok": False, "code": "registration_failed", "submitted": False, "error": detail_text}
    return {"ok": True, "submitted": True, **result}


def accounts_login(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    email = str(body.get("email", "")).strip()
    password = str(body.get("password", ""))
    if not email or not password:
        return {"ok": False, "error": "email and password are required"}
    if not _valid_email(email):
        return {"ok": False, "error": "Enter a valid email address."}
    if not _accounts_backend_ready():
        return {
            "ok": False,
            "code": "service_unavailable",
            "error": "Accounts are temporarily unavailable. Atlas works fully in local mode.",
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
            "error": "Accounts are temporarily unavailable. Atlas works fully in local mode.",
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
        return {"ok": False, "error": result.get("detail", "Enable account failed.")}
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


def _admin_result(result: Dict[str, Any], key: str, fail: str) -> Dict[str, Any]:
    if isinstance(result, list):
        return {"ok": True, key: result}
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", fail)}
    return {"ok": True, key: result}


def accounts_admin_dashboard(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return _admin_result(accounts_client.get_admin_dashboard(), "dashboard", "Admin access required.")


def accounts_admin_audit_log(_body: Dict[str, Any], query: Dict[str, str]) -> Dict[str, Any]:
    try:
        limit = int(query.get("limit", "100"))
    except (TypeError, ValueError):
        limit = 100
    return _admin_result(accounts_client.get_admin_audit_log(limit=limit), "entries", "Admin access required.")


def accounts_admin_grant_beta(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    return _admin_result(accounts_client.admin_grant_beta(uid), "user", "Enable account failed.")


def accounts_admin_revoke_beta(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    return _admin_result(accounts_client.admin_revoke_beta(uid), "user", "Disable account failed.")


def accounts_admin_force_logout(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    result = accounts_client.admin_force_logout(uid)
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Force logout failed.")}
    return {"ok": True}


def accounts_admin_update_user(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    uid = str(body.get("user_id", "")).strip()
    if not uid:
        return {"ok": False, "error": "user_id required"}
    fields = {k: v for k, v in (body or {}).items() if k != "user_id"}
    return _admin_result(accounts_client.admin_update_user(uid, fields), "user", "Update failed.")


def accounts_service_status(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    if accounts_client.auth_mode() == "website":
        # A website-authority build has no local process to probe or spawn.
        # The UI remains local-first; login/register surface a neutral fallback
        # if the remote authority cannot be reached.
        return {"running": True, "authority": "website"}
    running = accounts_client.is_service_running()
    if not running:
        running = accounts_service_runner.ensure_running(timeout=8.0)
    return {"running": running}


def accounts_validate_invite(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    code = str(body.get("code") or "").strip()
    if not code:
        return {"ok": False, "valid": False, "message": "Enter an access code."}
    if not accounts_service_runner.ensure_running(timeout=8.0):
        return {"ok": False, "valid": False, "message": "Accounts service unavailable."}
    result = accounts_client.validate_invite_code(code)
    if result.get("_offline"):
        return {"ok": False, "valid": False, "message": "Accounts service unavailable."}
    return {"ok": True, **result}


def accounts_acquisition_event(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    stage = str(body.get("stage") or "").strip()
    if not stage:
        return {"ok": False, "error": "stage required"}
    if accounts_service_runner.ensure_running(timeout=4.0):
        accounts_client.record_acquisition_event(
            stage,
            source=str(body.get("source") or "desktop"),
            metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
        )
    return {"ok": True}


def _admin_proxy(result: Dict[str, Any], key: str, fail: str) -> Dict[str, Any]:
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        detail = result.get("detail", fail)
        return {"ok": False, "error": detail if isinstance(detail, str) else str(detail)}
    return {"ok": True, key: result}


def accounts_admin_launch_readiness(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_launch_readiness()
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        detail = result.get("detail", "Launch readiness unavailable.")
        return {"ok": False, "error": detail if isinstance(detail, str) else str(detail)}
    return {"ok": True, "readiness": result}


def accounts_admin_feedback(_body: Dict[str, Any], query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_admin_feedback(
        status=query.get("status"),
        category=query.get("category"),
        limit=int(query.get("limit") or 100),
    )
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Feedback unavailable.")}
    if isinstance(result, list):
        return {"ok": True, "items": result}
    return {"ok": True, "items": result if isinstance(result, list) else []}


def accounts_admin_feedback_update(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    fid = str(body.get("feedback_id") or "").strip()
    status = str(body.get("status") or "").strip()
    if not fid or not status:
        return {"ok": False, "error": "feedback_id and status required"}
    return _admin_proxy(accounts_client.patch_admin_feedback(fid, status), "feedback", "Update failed.")


def accounts_admin_invites_list(_body: Dict[str, Any], query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.list_invite_codes(limit=int(query.get("limit") or 50))
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if isinstance(result, list):
        return {"ok": True, "invites": result}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Access codes unavailable.")}
    return {"ok": True, "invites": []}


def accounts_admin_invites_create(body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    return _admin_proxy(
        accounts_client.create_invite_code(
            email=str(body.get("email") or "").strip() or None,
            max_uses=int(body.get("max_uses") or 1),
            expires_days=int(body["expires_days"]) if body.get("expires_days") is not None else 30,
            notes=str(body.get("notes") or "").strip() or None,
        ),
        "invite",
        "Create access code failed.",
    )


def accounts_admin_export_beta(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.export_beta_users_admin()
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Export failed.")}
    return {"ok": True, "users": result.get("users") or []}


def accounts_admin_interview_summary(_body: Dict[str, Any], _query: Dict[str, str]) -> Dict[str, Any]:
    result = accounts_client.get_interview_summary()
    if result.get("_unauthenticated"):
        return {"ok": False, "error": "Admin account sign-in required."}
    if result.get("_http_status"):
        return {"ok": False, "error": result.get("detail", "Summary unavailable.")}
    return {"ok": True, "summary": result}


ACCOUNTS_ROUTES = {
    ("GET",  "/api/accounts/state"):          accounts_state,
    ("POST", "/api/accounts/register"):       accounts_register,
    ("POST", "/api/accounts/login"):          accounts_login,
    ("POST", "/api/accounts/logout"):         accounts_logout,
    ("POST", "/api/accounts/guest/start"):    accounts_guest_start,
    ("POST", "/api/accounts/guest/clear"):    accounts_guest_clear,
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
    # Phase 193 — Admin Console
    ("GET",  "/api/accounts/admin/dashboard"): accounts_admin_dashboard,
    ("GET",  "/api/accounts/admin/audit-log"): accounts_admin_audit_log,
    ("POST", "/api/accounts/admin/users/grant-beta"): accounts_admin_grant_beta,
    ("POST", "/api/accounts/admin/users/revoke-beta"): accounts_admin_revoke_beta,
    ("POST", "/api/accounts/admin/users/force-logout"): accounts_admin_force_logout,
    ("POST", "/api/accounts/admin/users/update"): accounts_admin_update_user,
    # Phase 199 — legacy account acquisition compatibility
    ("POST", "/api/accounts/validate-invite"): accounts_validate_invite,
    ("POST", "/api/accounts/acquisition/event"): accounts_acquisition_event,
    ("GET",  "/api/accounts/admin/launch-readiness"): accounts_admin_launch_readiness,
    ("GET",  "/api/accounts/admin/feedback"): accounts_admin_feedback,
    ("POST", "/api/accounts/admin/feedback/update"): accounts_admin_feedback_update,
    ("GET",  "/api/accounts/admin/invites"): accounts_admin_invites_list,
    ("POST", "/api/accounts/admin/invites"): accounts_admin_invites_create,
    ("GET",  "/api/accounts/admin/export/beta-users"): accounts_admin_export_beta,
    ("GET",  "/api/accounts/admin/interview-summary"): accounts_admin_interview_summary,
}
