"""Shared pytest fixtures for atlas_desktop tests."""
from __future__ import annotations

import pytest

from atlas_desktop import server


# A signed-in beta user with an active license — the realistic precondition for
# account/license-gated routes. This simulates authentication for the test harness
# only. It does NOT change the production gate (server._account_gate_failure), which
# still enforces beta access for real, unauthenticated callers.
_AUTHENTICATED_BETA_STATE = {
    "authenticated": True,
    "signed_in": True,
    "user": {"user_id": "test-beta-user", "email": "beta@test.local"},
    "license": {"valid": True, "plan": "beta", "status": "active"},
    "device_id": "test-device",
    "service_online": True,
    "state_integrity_error": False,
    "last_auth_error": None,
}


@pytest.fixture
def beta_account(monkeypatch):
    """Make account/license-gated routes reachable by simulating a signed-in beta
    user with an active license.

    Opt-in: request it by name in tests that exercise gated routes. The monkeypatch
    auto-reverts at teardown, so it never leaks auth state into other tests, and the
    real gate logic is left untouched.
    """
    monkeypatch.setattr(
        server.accounts_client,
        "get_account_state",
        lambda: dict(_AUTHENTICATED_BETA_STATE),
    )
    return dict(_AUTHENTICATED_BETA_STATE)
