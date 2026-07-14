"""Shared pytest fixtures for atlas_desktop tests."""
from __future__ import annotations

import os
import hashlib
import tempfile
import uuid
from pathlib import Path

# Establish a non-user quarantine before importing any Atlas module. Test
# collection itself imports server/api modules, so a normal pytest fixture is
# too late to protect the canonical registry.
_REAL_USER_HOME = Path(os.environ.get("USERPROFILE") or Path.home()).resolve()
_PROTECTED_DATA_ROOT = _REAL_USER_HOME / ".atlas_desktop"
_COLLECTION_DATA_ROOT = Path(tempfile.gettempdir()) / (
    f"atlas-pytest-collection-{os.getpid()}-{uuid.uuid4().hex}"
)
os.environ["ATLAS_TEST_MODE"] = "1"
os.environ["ATLAS_TEST_PROTECTED_DATA_ROOT"] = str(_PROTECTED_DATA_ROOT)
os.environ["ATLAS_TEST_RUN_ID"] = uuid.uuid4().hex
os.environ["ATLAS_DESKTOP_DATA"] = str(_COLLECTION_DATA_ROOT)
os.environ["JARVIS_DESKTOP_DATA"] = str(_COLLECTION_DATA_ROOT)


def _protected_scan_fingerprint() -> tuple[str, tuple[tuple[str, int, int], ...]]:
    scans = _PROTECTED_DATA_ROOT / "scans"
    registry = scans / "registry.json"
    registry_hash = "missing"
    if registry.is_file():
        registry_hash = hashlib.sha256(registry.read_bytes()).hexdigest()
    entries = []
    if scans.is_dir():
        for path in sorted(scans.rglob("*")):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
                entries.append((str(path.relative_to(scans)), stat.st_size, stat.st_mtime_ns))
            except OSError:
                entries.append((str(path.relative_to(scans)), -1, -1))
    return registry_hash, tuple(entries)


_PROTECTED_SCAN_FINGERPRINT = _protected_scan_fingerprint()

import pytest

from atlas_desktop import server
from atlas_desktop import data_paths


@pytest.fixture(scope="session", autouse=True)
def canonical_scan_tree_must_not_change():
    """Fail the entire run if any test mutates the real registry or scan tree."""
    yield
    assert _protected_scan_fingerprint() == _PROTECTED_SCAN_FINGERPRINT


@pytest.fixture(autouse=True)
def isolated_atlas_data_root(tmp_path, monkeypatch, request):
    """Give every test and inherited child process a unique Atlas data root."""
    root = tmp_path / f"atlas-data-{uuid.uuid4().hex}"
    monkeypatch.setenv("ATLAS_TEST_MODE", "1")
    monkeypatch.setenv("ATLAS_TEST_PROTECTED_DATA_ROOT", str(_PROTECTED_DATA_ROOT))
    monkeypatch.setenv("ATLAS_TEST_RUN_ID", f"{os.getpid()}-{request.node.nodeid}")
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(root))
    monkeypatch.setenv("JARVIS_DESKTOP_DATA", str(root))
    data_paths.reset_desktop_data_dir_cache()
    yield root
    data_paths.reset_desktop_data_dir_cache()


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


@pytest.fixture
def local_guest_account(monkeypatch):
    """Make local-workflow routes reachable by simulating the UI Guest Mode choice.

    Direct API tests do not click the first-launch auth screen, so they need to
    opt in to the same local-only entitlement that the UI creates.
    """
    state = {
        "authenticated": False,
        "signed_in": False,
        "local_access": True,
        "guest": True,
        "guest_id": "00000000-0000-4000-8000-000000000001",
        "license": {
            "valid": True,
            "plan": "guest",
            "status": "guest_local",
            "local_only": True,
        },
        "device_id": "test-guest-device",
        "service_online": False,
        "state_integrity_error": False,
        "last_auth_error": None,
    }
    monkeypatch.setattr(server.accounts_client, "get_account_state", lambda: dict(state))
    return dict(state)
