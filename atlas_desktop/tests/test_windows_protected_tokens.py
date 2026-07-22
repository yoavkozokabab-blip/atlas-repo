from __future__ import annotations

import json
import os
import time

import pytest

from atlas_desktop import accounts_client
from atlas_desktop import protected_storage


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI is required")


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(accounts_client, "desktop_data_dir", lambda: str(tmp_path))
    return tmp_path


def _session_state() -> dict:
    return {
        "device_id": "device-1",
        "access_token": "access-secret",
        "access_token_expires_at": time.time() + 3600,
        "refresh_token": "refresh-secret",
        "user": {"user_id": "user-1", "email": "safe@example.test"},
        "license": {"valid": True, "plan": "free", "status": "active"},
        "license_checked_at": time.time(),
    }


def test_dpapi_round_trip_does_not_leave_plaintext():
    raw = b'access-token-marker'
    protected = protected_storage.protect_bytes(raw)

    assert protected_storage.unprotect_bytes(protected) == raw
    assert raw not in protected


def test_dpapi_uses_current_user_scope_only():
    # CRYPTPROTECT_LOCAL_MACHINE (0x4) must never be set. Its absence makes the
    # DPAPI blob decryptable only by the Windows user that protected it.
    assert protected_storage._CRYPTPROTECT_UI_FORBIDDEN == 0x01
    assert protected_storage._CRYPTPROTECT_UI_FORBIDDEN & 0x04 == 0


def test_tokens_are_protected_outside_state_json(isolated_state):
    accounts_client._save_state(_session_state())

    state_text = (isolated_state / "accounts_state.json").read_text(encoding="utf-8")
    protected = (isolated_state / "accounts_credentials.dpapi").read_bytes()
    restored = accounts_client._load_state()

    assert "access-secret" not in state_text
    assert "refresh-secret" not in state_text
    assert b"access-secret" not in protected
    assert b"refresh-secret" not in protected
    assert restored["access_token"] == "access-secret"
    assert restored["refresh_token"] == "refresh-secret"


def test_legacy_plaintext_state_is_migrated_once(isolated_state):
    legacy = _session_state()
    accounts_client._write_state_file(legacy)
    assert "access-secret" in (isolated_state / "accounts_state.json").read_text(encoding="utf-8")

    restored = accounts_client._load_state()
    migrated = (isolated_state / "accounts_state.json").read_text(encoding="utf-8")

    assert restored["access_token"] == "access-secret"
    assert "access-secret" not in migrated
    assert "refresh-secret" not in migrated
    assert (isolated_state / "accounts_credentials.dpapi").is_file()


def test_failed_legacy_migration_removes_plaintext_tokens(isolated_state, monkeypatch):
    legacy = _session_state()
    accounts_client._write_state_file(legacy)
    monkeypatch.setattr(
        accounts_client,
        "encode_credentials",
        lambda _credentials: (_ for _ in ()).throw(
            protected_storage.ProtectedStorageError("unavailable")
        ),
    )

    restored = accounts_client._load_state()
    state_text = (isolated_state / "accounts_state.json").read_text(encoding="utf-8")

    assert restored["_state_integrity_error"] is True
    assert "access-secret" not in state_text
    assert "refresh-secret" not in state_text


def test_corrupted_protected_blob_fails_closed(isolated_state):
    accounts_client._save_state(_session_state())
    (isolated_state / "accounts_credentials.dpapi").write_bytes(b"not-a-dpapi-blob")

    restored = accounts_client._load_state()

    assert restored["_state_integrity_error"] is True
    assert "access_token" not in restored
    assert "refresh_token" not in restored


def test_logout_deletes_protected_credentials(isolated_state, monkeypatch):
    accounts_client._save_state(_session_state())
    monkeypatch.setattr(accounts_client, "auth_mode", lambda: "website")
    monkeypatch.setattr(accounts_client, "_call", lambda *args, **kwargs: {"ok": True})

    accounts_client.logout()

    assert not (isolated_state / "accounts_credentials.dpapi").exists()
    state = json.loads((isolated_state / "accounts_state.json").read_text(encoding="utf-8"))
    assert "access_token" not in state
    assert "refresh_token" not in state


def test_offline_session_token_restores_from_dpapi(isolated_state, monkeypatch):
    accounts_client._save_state(_session_state())
    monkeypatch.setattr(accounts_client, "auth_mode", lambda: "website")

    assert accounts_client.get_valid_access_token() == "access-secret"
