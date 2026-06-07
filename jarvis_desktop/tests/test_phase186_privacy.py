"""Phase 186 — Privacy & redaction tests.

These tests prove that:
  1. The PrivacyValidator rejects any analytics payload containing:
     - Unexpected string fields (potential code / path exfiltration)
     - Values matching secret patterns (API keys, bearer tokens, file paths)
  2. Only whitelisted string fields (event_type, app_version, date) are accepted
  3. Integer-only counter fields are accepted without restriction
  4. The analytics endpoint enforces the validator (returns 422 for bad payloads)
  5. No source code, file paths, or repository contents can be sent through
     the analytics endpoint
  6. accounts_client.send_analytics_event() only constructs whitelisted payloads
"""
from __future__ import annotations

import os
import re
import secrets
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_LIB = os.path.join(_ROOT, "accounts_service", ".lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ.setdefault("ATLAS_ACCOUNTS_DB", "sqlite:///./test_privacy_186.db")
os.environ.setdefault("ATLAS_JWT_SECRET", "privacy-test-secret-186")

from fastapi.testclient import TestClient
from accounts_service.main import app
from accounts_service.database import Base, engine
from accounts_service.routers.analytics import PrivacyValidator, ALLOWED_EVENT_TYPES

# ── DB setup ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    for f in ["test_privacy_186.db"]:
        if os.path.exists(f):
            try:
                os.unlink(f)
            except OSError:
                pass


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client):
    """Get an access token for a fresh test user."""
    email = f"privacy_{secrets.token_hex(6)}@test.dev"
    device = secrets.token_hex(16)
    r = client.post("/auth/register", json={
        "email": email, "password": "PrivacyTest1!",
        "device_id": device, "app_version": "0.1.0-beta", "platform": "test"
    })
    return r.json()["access_token"], device


# ── PrivacyValidator unit tests ───────────────────────────────────────────────

class TestPrivacyValidatorUnit:
    """Direct unit tests of the PrivacyValidator class."""

    def test_allowed_string_fields_pass(self):
        """Whitelisted string fields must not raise."""
        PrivacyValidator.validate({
            "event_type": "app_started",
            "app_version": "0.1.0-beta",
            "date": "2026-06-07",
        })

    def test_unexpected_string_field_raises(self):
        """Any string field outside the whitelist must raise."""
        with pytest.raises(ValueError, match="Unexpected string field"):
            PrivacyValidator.validate({
                "event_type": "app_started",
                "source_code": "def foo(): return 42",
            })

    def test_repository_path_field_raises(self):
        with pytest.raises(ValueError, match="Unexpected string field"):
            PrivacyValidator.validate({
                "event_type": "scan_completed",
                "repo_path": "C:\\Users\\dev\\my-project",
            })

    def test_raw_prompt_field_raises(self):
        with pytest.raises(ValueError, match="Unexpected string field"):
            PrivacyValidator.validate({
                "event_type": "change_plan_generated",
                "prompt": "Add a new API endpoint for user registration",
            })

    def test_file_contents_field_raises(self):
        with pytest.raises(ValueError, match="Unexpected string field"):
            PrivacyValidator.validate({
                "event_type": "export_copied",
                "file_contents": "import os\nprint('hello')",
            })

    def test_api_key_in_event_type_raises(self):
        """Secret pattern in a whitelisted field must raise."""
        with pytest.raises(ValueError):
            PrivacyValidator.validate({
                "event_type": "sk-abcdef12345678",  # looks like an API key
            })

    def test_bearer_token_in_app_version_raises(self):
        with pytest.raises(ValueError):
            PrivacyValidator.validate({
                "app_version": "bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
            })

    def test_path_in_app_version_raises(self):
        with pytest.raises(ValueError):
            PrivacyValidator.validate({
                "app_version": "/home/user/secret/config.env",
            })

    def test_integer_fields_always_allowed(self):
        """Counter fields (integers) must never trigger the validator."""
        PrivacyValidator.validate({
            "event_type": "heartbeat",
            "launches": 1,
            "scans": 5,
            "change_plans": 2,
            "debug_runs": 0,
            "what_breaks_runs": 0,
            "exports": 1,
            "estimated_tokens_saved": 12345,
        })

    def test_none_values_allowed(self):
        """None values (not strings) must not trigger the string check."""
        PrivacyValidator.validate({
            "event_type": "heartbeat",
            "app_version": None,
        })

    def test_event_type_length_limit(self):
        with pytest.raises(ValueError, match="event_type too long"):
            PrivacyValidator.validate({
                "event_type": "x" * 65,
            })

    def test_app_version_length_limit(self):
        with pytest.raises(ValueError, match="app_version too long"):
            PrivacyValidator.validate({
                "app_version": "0." + "1" * 40,
            })

    def test_windows_path_rejected_in_any_whitelisted_field(self):
        """A Windows path in the date field must be caught by the secret pattern."""
        with pytest.raises(ValueError):
            PrivacyValidator.validate({
                "event_type": "heartbeat",
                "date": "C:\\Users\\dev\\project",
            })


class TestAllowedEventTypes:
    """ALLOWED_EVENT_TYPES whitelist is exhaustive and predictable."""

    def test_only_safe_event_types_allowed(self):
        safe = {
            "app_started", "scan_completed", "change_plan_generated",
            "debug_generated", "what_breaks_generated", "export_copied",
            "feedback_submitted", "heartbeat",
        }
        assert ALLOWED_EVENT_TYPES == safe

    def test_no_source_code_event_types(self):
        dangerous = {"source_code_uploaded", "file_contents", "repo_exported", "prompt_sent"}
        assert not dangerous.intersection(ALLOWED_EVENT_TYPES)


class TestAnalyticsEndpointEnforcement:
    """The /analytics/event HTTP endpoint must enforce the privacy validator."""

    def test_valid_event_accepted(self, client, auth_token):
        token, device = auth_token
        res = client.post("/analytics/event",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": device, "event_type": "app_started",
                "app_version": "0.1.0-beta", "date": "2026-06-07",
                "launches": 1, "scans": 0, "change_plans": 0,
                "debug_runs": 0, "what_breaks_runs": 0,
                "exports": 0, "estimated_tokens_saved": 0,
            }
        )
        assert res.status_code == 204

    def test_source_code_field_rejected(self, client, auth_token):
        token, device = auth_token
        res = client.post("/analytics/event",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": device, "event_type": "scan_completed",
                "app_version": "0.1.0", "date": "2026-06-07",
                "launches": 0, "scans": 1, "change_plans": 0,
                "debug_runs": 0, "what_breaks_runs": 0,
                "exports": 0, "estimated_tokens_saved": 0,
                "source_code": "def secret_function(): return api_key",
            }
        )
        assert res.status_code == 422

    def test_path_field_rejected(self, client, auth_token):
        token, device = auth_token
        res = client.post("/analytics/event",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": device, "event_type": "heartbeat",
                "app_version": "0.1.0", "date": "2026-06-07",
                "launches": 0, "scans": 0, "change_plans": 0,
                "debug_runs": 0, "what_breaks_runs": 0,
                "exports": 0, "estimated_tokens_saved": 0,
                "repo_path": "/home/user/secrets",
            }
        )
        assert res.status_code == 422

    def test_negative_counters_rejected(self, client, auth_token):
        """Counter fields must be non-negative integers."""
        token, device = auth_token
        res = client.post("/analytics/event",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "device_id": device, "event_type": "app_started",
                "app_version": "0.1.0", "date": "2026-06-07",
                "launches": -1, "scans": 0, "change_plans": 0,
                "debug_runs": 0, "what_breaks_runs": 0,
                "exports": 0, "estimated_tokens_saved": 0,
            }
        )
        assert res.status_code == 422

    def test_unauthenticated_analytics_rejected(self, client):
        res = client.post("/analytics/event", json={
            "device_id": secrets.token_hex(16), "event_type": "heartbeat",
            "app_version": "0.1.0", "date": "2026-06-07",
            "launches": 1, "scans": 0, "change_plans": 0,
            "debug_runs": 0, "what_breaks_runs": 0,
            "exports": 0, "estimated_tokens_saved": 0,
        })
        assert res.status_code == 401


class TestAccountsClientPayloadConstruction:
    """Verify accounts_client.send_analytics_event() only builds safe payloads."""

    def test_payload_only_has_whitelisted_string_fields(self):
        """Inspect what send_analytics_event would send — no string smuggling."""
        # We test the payload structure without making a real HTTP call
        import inspect, ast

        # Load the accounts_client source
        client_path = os.path.join(_ROOT, "jarvis_desktop", "accounts_client.py")
        with open(client_path, encoding="utf-8") as f:
            source = f.read()

        # The payload dict literal in send_analytics_event must not contain
        # any non-whitelisted string fields
        WHITELISTED = {"device_id", "event_type", "app_version", "date",
                       "launches", "scans", "change_plans", "debug_runs",
                       "what_breaks_runs", "exports", "estimated_tokens_saved"}

        # Check that no other string keys are referenced in the function
        # Simple keyword check: no "source_code", "repo_path", "prompt", "file_contents"
        forbidden = ["source_code", "repo_path", "raw_prompt", "file_contents", "export_text"]
        for bad_key in forbidden:
            assert bad_key not in source, (
                f"accounts_client.py must not reference {bad_key!r} in analytics payloads"
            )

    def test_extra_counters_are_validated_against_known_keys(self):
        """send_analytics_event only copies known integer keys."""
        # Import and inspect
        sys.path.insert(0, os.path.join(_ROOT, "jarvis_desktop"))
        try:
            import importlib, types
            # We cannot run it (needs desktop_data_dir), but can parse the source
            client_path = os.path.join(_ROOT, "jarvis_desktop", "accounts_client.py")
            with open(client_path, encoding="utf-8") as f:
                src = f.read()
            # Verify the guard: `if k in payload and isinstance(v, int)`
            assert "if k in payload and isinstance(v, int)" in src, (
                "send_analytics_event must guard against unknown counter keys"
            )
        finally:
            pass
