"""Regression tests for local accounts-service readiness in the desktop proxy."""
from __future__ import annotations

from unittest.mock import patch

from atlas_desktop import accounts_client, accounts_routes


def _profile() -> dict:
    return {
        "currently_developer": True,
        "project_use": "work",
        "company_size": "11_50",
        "developer_experience": "3_5",
        "primary_role": "backend",
        "coding_tools": ["claude"],
        "repo_size": "medium",
        "atlas_help": ["planning_changes"],
    }


def test_service_running_requires_invite_validation_probe():
    def broken_call(_method, path, payload=None, access_token=None, base=None):
        if path == "/health":
            return {"status": "ok", "service": "atlas-accounts"}
        if path == "/acquisition/validate-invite":
            return {"_http_status": 500, "detail": "Internal Server Error"}
        raise AssertionError(path)

    with patch("atlas_desktop.accounts_client.auth_mode", return_value="local"):
        with patch("atlas_desktop.accounts_client._call", side_effect=broken_call):
            assert accounts_client.is_service_running() is False

    def ready_call(_method, path, payload=None, access_token=None, base=None):
        if path == "/health":
            return {"status": "ok", "service": "atlas-accounts"}
        if path == "/acquisition/validate-invite":
            return {"valid": False, "message": "Invite code not found."}
        raise AssertionError(path)

    with patch("atlas_desktop.accounts_client.auth_mode", return_value="local"):
        with patch("atlas_desktop.accounts_client._call", side_effect=ready_call):
            assert accounts_client.is_service_running() is True


def test_backend_500_is_not_shown_as_registration_error():
    with patch("atlas_desktop.accounts_service_runner.ensure_running", return_value=True):
        with patch(
            "atlas_desktop.accounts_client.register",
            return_value={"_http_status": 500, "detail": "Internal Server Error"},
        ):
            out = accounts_routes.accounts_register({
                "email": "backend500@example.com",
                "password": "SecurePass1!",
                "confirm_password": "SecurePass1!",
                "beta_profile": _profile(),
            }, {})

    assert out["ok"] is False
    assert out["code"] == "service_unavailable"
    assert out["submitted"] is False
    assert "Internal Server Error" not in out.get("error", "")


def test_website_authority_login_never_starts_the_legacy_helper():
    with patch("atlas_desktop.accounts_client.auth_mode", return_value="website"):
        with patch("atlas_desktop.accounts_service_runner.ensure_running") as ensure:
            with patch("atlas_desktop.accounts_client.login", return_value={"ok": True, "token": "opaque"}):
                out = accounts_routes.accounts_login({"email": "person@example.com", "password": "SecurePass1!"}, {})

    assert out["ok"] is True
    ensure.assert_not_called()


def test_website_authority_outage_has_a_neutral_local_fallback_message():
    with patch("atlas_desktop.accounts_client.auth_mode", return_value="website"):
        with patch("atlas_desktop.accounts_service_runner.ensure_running") as ensure:
            with patch("atlas_desktop.accounts_client.login", return_value={"_offline": True}):
                out = accounts_routes.accounts_login({"email": "person@example.com", "password": "SecurePass1!"}, {})

    assert out["code"] == "service_unavailable"
    assert out["error"] == "Accounts are temporarily unavailable. Atlas works fully in local mode."
    ensure.assert_not_called()
