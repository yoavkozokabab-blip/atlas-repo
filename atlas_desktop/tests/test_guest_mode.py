"""Guest Mode: local-only entitlement without weakening real account auth."""
from __future__ import annotations

import importlib
import json
import os
import base64
import time
import uuid
from pathlib import Path

import pytest


@pytest.fixture()
def isolated_accounts(monkeypatch):
    root = Path(os.environ.get("ATLAS_GUEST_TEST_ROOT", r"C:\J.A.R.V.I.S\atlas_guest_test_data"))
    data_dir = root / f"run_{uuid.uuid4().hex}" / "atlas_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(data_dir))
    monkeypatch.setenv("ATLAS_AUTH_MODE", "website")
    from atlas_desktop import data_paths
    from atlas_desktop import accounts_client

    data_paths.reset_desktop_data_dir_cache()
    importlib.reload(accounts_client)
    yield accounts_client
    data_paths.reset_desktop_data_dir_cache()


def test_guest_start_is_local_signed_state_without_network(isolated_accounts, monkeypatch):
    calls = []
    monkeypatch.setattr(isolated_accounts, "_call", lambda *a, **k: calls.append((a, k)) or {"ok": False})

    started = isolated_accounts.start_guest_session()

    assert started["ok"] is True
    assert started["guest"] is True
    assert started["authenticated"] is False
    assert started["signed_in"] is False
    assert started["local_access"] is True
    assert started["plan"] == "guest"
    assert started["status"] == "guest_local"
    assert started["user"] is None
    assert calls == []

    restored = isolated_accounts.get_account_state()
    assert restored["guest_id"] == started["guest_id"]
    assert restored["local_access"] is True


def test_malformed_guest_state_fails_closed(isolated_accounts):
    isolated_accounts._save_state({"guest": True})

    state = isolated_accounts.get_account_state()

    assert state["guest"] is False
    assert state["authenticated"] is False
    assert state["local_access"] is False


def test_restricted_real_account_state_cannot_start_guest(isolated_accounts):
    isolated_accounts._save_state({
        "user": {"user_id": "u1", "email": "blocked@example.com", "status": "suspended"},
        "license": {"valid": False, "status": "suspended"},
    })

    res = isolated_accounts.start_guest_session()

    assert res["ok"] is False
    assert res["code"] == "real_account_restricted"
    assert isolated_accounts.get_account_state()["guest"] is False


def test_guest_allows_only_local_workflow_routes(monkeypatch):
    from atlas_desktop import server

    guest = {
        "authenticated": False,
        "signed_in": False,
        "guest": True,
        "local_access": True,
        "user": None,
        "license": {"valid": True, "plan": "guest", "status": "guest_local"},
    }
    monkeypatch.setattr(server.accounts_client, "get_account_state", lambda: dict(guest))
    monkeypatch.setattr(server.api, "load_demo_mode", lambda pack="medium": {"ok": True, "route": "demo"})
    monkeypatch.setattr(server.api, "scan_repository", lambda path=None, scope=None: {"ok": True, "route": "scan"})
    monkeypatch.setattr(server.api, "impact", lambda target="": {"ok": True, "route": "impact"})
    monkeypatch.setattr(server.api, "plan_change", lambda request="": {"ok": True, "route": "plan"})
    monkeypatch.setattr(server.api, "investigate_symptom", lambda symptom="": {"ok": True, "route": "debug"})
    monkeypatch.setattr(server.api, "change_impact_simulation", lambda target="": {"ok": True, "route": "planning-impact"})
    monkeypatch.setattr(server.api, "bug_investigation", lambda text="": {"ok": True, "route": "bug"})
    monkeypatch.setattr(server.api, "context_export", lambda target="claude", packet="compact": {"ok": True, "route": "context"})
    monkeypatch.setattr(server.api, "agent_export", lambda target="claude", task="", max_files=12: {"ok": True, "route": "agent"})
    monkeypatch.setattr(server.api, "write_cursor_rule", lambda task="": {"ok": True, "route": "cursor-rule"})
    monkeypatch.setattr(server.api, "write_claude_code_block", lambda task="": {"ok": True, "route": "claude-block"})
    monkeypatch.setattr(server.api, "copilot_ask", lambda question="", target="none", packet="compact", node_context=None: {"ok": True, "route": "ask"})

    for method, path in sorted(server.PROTECTED_ACCOUNT_ROUTES):
        status, payload = server.dispatch(method, path, {"question": "Where is authentication implemented?"})
        assert status == 200, (method, path, payload)
        assert payload.get("code") != "account_required"

    for method, path in (
        ("GET", "/api/accounts/profile"),
        ("GET", "/api/accounts/devices"),
        ("GET", "/api/accounts/admin/users"),
        ("GET", "/api/accounts/admin/dashboard"),
    ):
        status, payload = server.dispatch(method, path, {})
        assert status == 200
        assert payload["ok"] is False, (method, path, payload)


def test_guest_to_sign_in_preserves_local_repository_data(isolated_accounts, monkeypatch):
    data_dir = Path(os.environ["ATLAS_DESKTOP_DATA"])
    registry = data_dir / "scans" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps({"items": [{"repo_id": "local-repo"}]}), encoding="utf-8")

    guest = isolated_accounts.start_guest_session()
    assert guest["local_access"] is True

    payload = json.dumps({"exp": int(time.time()) + 3600}).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=") + ".sig"

    def fake_call(method, path, body=None, access_token=None, base=None):
        assert path in {"/api/auth/desktop/login", "/api/auth/desktop/me"}
        return {
            "ok": True,
            "token": token if path.endswith("/login") else None,
            "user": {"id": "supabase-user-1", "email": "dev@example.com", "status": "active"},
            "entitlement": {"approved": True, "plan": "free"},
        }

    monkeypatch.setattr(isolated_accounts, "_call", fake_call)
    signed_in = isolated_accounts.login("dev@example.com", "password123", "1.0.0", "test")

    assert signed_in["ok"] is True
    state = isolated_accounts.get_account_state()
    assert state["guest"] is False
    assert state["authenticated"] is True
    assert registry.exists()
    assert json.loads(registry.read_text(encoding="utf-8"))["items"][0]["repo_id"] == "local-repo"
