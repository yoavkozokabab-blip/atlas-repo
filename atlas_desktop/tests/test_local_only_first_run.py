"""v1.0.5 launch: local-only first run when account helper / port / Supabase are unavailable."""
from __future__ import annotations

import importlib
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
ACCOUNTS_JS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")

LOCAL_ONLY_NOTE = (
    "Accounts are temporarily unavailable. Atlas works fully in local mode."
)


@pytest.fixture()
def isolated_accounts(monkeypatch, tmp_path):
    data_dir = tmp_path / f"run_{uuid.uuid4().hex}" / "atlas_data"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(data_dir))
    monkeypatch.delenv("ATLAS_ACCOUNTS_UI_MODE", raising=False)
    monkeypatch.setenv("ATLAS_AUTH_MODE", "website")
    from atlas_desktop import data_paths
    from atlas_desktop import accounts_client

    data_paths.reset_desktop_data_dir_cache()
    importlib.reload(accounts_client)
    yield accounts_client
    data_paths.reset_desktop_data_dir_cache()


def test_default_accounts_ui_mode_is_local_only(isolated_accounts):
    assert isolated_accounts.accounts_ui_mode() == "local_only"
    state = isolated_accounts.get_account_state()
    assert state["accounts_ui_mode"] == "local_only"
    assert state["authenticated"] is False
    assert state["local_access"] is False


def test_full_accounts_ui_mode_override(isolated_accounts, monkeypatch):
    monkeypatch.setenv("ATLAS_ACCOUNTS_UI_MODE", "full")
    importlib.reload(isolated_accounts)
    assert isolated_accounts.accounts_ui_mode() == "full"
    assert isolated_accounts.get_account_state()["accounts_ui_mode"] == "full"


def test_first_run_ui_hides_sign_in_and_create_account():
    assert 'id="acc-guest-btn"' in INDEX
    assert "Continue without an account" in INDEX
    assert 'id="acc-login-btn"' in INDEX
    assert "Sign In" in INDEX
    assert 'id="acc-create-btn"' in INDEX
    assert "Create free account" in INDEX
    assert 'hidden disabled' in INDEX
    assert LOCAL_ONLY_NOTE in INDEX
    assert "atlas-local-only-auth" in CSS
    assert "body.atlas-local-only-auth #acc-login-btn" in CSS
    assert "body.atlas-local-only-auth #acc-create-btn" in CSS
    assert "body.atlas-local-only-auth #acc-login-error" in CSS
    assert "auth-local-only-note" in CSS


def test_first_run_js_defaults_local_only_and_suppresses_red_error():
    assert "_accountsUiMode = 'local_only'" in ACCOUNTS_JS
    assert LOCAL_ONLY_NOTE in ACCOUNTS_JS
    assert "_applyAccountsUiMode(_accountsUiMode)" in ACCOUNTS_JS
    assert "if (_isLocalOnlyLaunch()) return;" in ACCOUNTS_JS
    assert "account_service_unavailable" not in INDEX
    assert "account_service_unavailable" not in ACCOUNTS_JS
    # Guest is the primary action; Sign In is not auto-attempted on init.
    assert "api('POST', '/api/accounts/login'" in ACCOUNTS_JS
    assert "function init()" in ACCOUNTS_JS
    init_block = ACCOUNTS_JS[ACCOUNTS_JS.find("function init()") : ACCOUNTS_JS.find("window.atlasAccounts")]
    assert "api('POST', '/api/accounts/login'" not in init_block
    assert "api('POST', '/api/accounts/register'" not in init_block
    assert "_applyAccountsUiMode" in init_block


def test_guest_local_mode_works_without_accounts_helper_or_supabase(isolated_accounts, monkeypatch):
    calls = []

    def blocked_call(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": False, "_offline": True, "error": "account_service_unavailable"}

    monkeypatch.setattr(isolated_accounts, "_call", blocked_call)
    with patch("atlas_desktop.accounts_service_runner.ensure_running", return_value=False):
        with patch("atlas_desktop.accounts_service_runner.start_accounts_service", return_value=False):
            started = isolated_accounts.start_guest_session()

    assert started["ok"] is True
    assert started["local_access"] is True
    assert started["guest"] is True
    assert started["accounts_ui_mode"] == "local_only"
    assert calls == []


def test_account_state_when_port_8779_and_helper_absent_still_allows_guest(isolated_accounts, monkeypatch):
    """Port 8779 is the desktop API; helper uses 8788. Neither is required for guest."""
    monkeypatch.setattr(
        isolated_accounts,
        "is_service_running",
        lambda: False,
    )
    started = isolated_accounts.start_guest_session()
    assert started["ok"] is True
    assert started["local_access"] is True
    state = isolated_accounts.get_account_state()
    assert state["local_access"] is True
    assert state["accounts_ui_mode"] == "local_only"


def test_website_auth_mode_does_not_require_atlasaccounts_process(isolated_accounts):
    assert isolated_accounts.auth_mode() == "website"
    assert isolated_accounts.is_service_running() is True  # website mode: no local helper


def test_account_failure_does_not_block_local_workflow_routes(monkeypatch, isolated_accounts):
    from atlas_desktop import server

    guest = isolated_accounts.start_guest_session()
    assert guest["local_access"] is True

    monkeypatch.setattr(server.accounts_client, "get_account_state", lambda: dict(guest))
    monkeypatch.setattr(server.api, "load_demo_mode", lambda pack="medium": {"ok": True, "route": "demo"})
    monkeypatch.setattr(server.api, "scan_repository", lambda path=None, scope=None: {"ok": True, "route": "scan"})
    monkeypatch.setattr(server.api, "impact", lambda target="": {"ok": True, "route": "impact"})
    monkeypatch.setattr(server.api, "plan_change", lambda request="": {"ok": True})
    monkeypatch.setattr(server.api, "investigate_symptom", lambda symptom="": {"ok": True})
    monkeypatch.setattr(server.api, "change_impact_simulation", lambda target="": {"ok": True})
    monkeypatch.setattr(server.api, "bug_investigation", lambda text="": {"ok": True})
    monkeypatch.setattr(
        server.api,
        "context_export",
        lambda target="claude", packet="compact": {"ok": True},
    )
    monkeypatch.setattr(
        server.api,
        "agent_export",
        lambda target="claude", task="", max_files=12: {"ok": True},
    )
    monkeypatch.setattr(server.api, "write_cursor_rule", lambda task="": {"ok": True})
    monkeypatch.setattr(server.api, "write_claude_code_block", lambda task="": {"ok": True})
    monkeypatch.setattr(
        server.api,
        "copilot_ask",
        lambda question="", target="none", packet="compact", node_context=None: {"ok": True},
    )

    for method, path in sorted(server.PROTECTED_ACCOUNT_ROUTES):
        status, payload = server.dispatch(method, path, {"question": "x", "target": "billing.py"})
        assert status == 200, (method, path, payload)
        assert payload.get("code") != "account_required"


def test_packaging_still_includes_accounts_helper_definition():
    """Account implementation is preserved for a later release — not deleted."""
    root = Path(__file__).resolve().parents[2]
    runner = (root / "atlas_desktop" / "accounts_service_runner.py").read_text(encoding="utf-8")
    build = (root / "packaging" / "pyinstaller" / "build_atlas_exe.ps1").read_text(encoding="utf-8")
    installer = (root / "packaging" / "installer" / "installer_build.ps1").read_text(encoding="utf-8")
    assert "AtlasAccounts.exe" in runner
    assert "start_accounts_service" in runner
    assert "AtlasAccounts" in build
    assert "AtlasAccounts.exe" in installer
