"""Phase 181K — final persistence regression fixes."""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, persistence, server
from atlas_desktop import repository_memory as rm


def _fresh() -> None:
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    return str(d)


def _mini_repo(tmp_path: Path) -> str:
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    return str(repo)


def test_fresh_scan_session_export_is_trusted(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    export = api.session_export_packet()
    assert export.get("ok") is True
    assert export.get("status") != "memory_untrusted"
    assert "ATLAS_REPOSITORY_MEMORY v1" in export.get("text", "")


def test_fresh_scan_memory_has_hmac(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    packet = api._STATE.get("session_export") or {}
    assert packet.get("memory_hmac")
    assert packet.get("mode") == "MEMORY"


def test_state_repository_memory_matches_current_memory(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    session = api._STATE.get("session_export") or {}
    repo_mem = api._STATE.get("repository_memory") or {}
    current = api._STATE.get("_current_memory") or {}
    assert session.get("memory_hmac") == repo_mem.get("memory_hmac")
    assert session.get("scan_id") == current.get("scan_id")
    assert session.get("repo_id") == current.get("repo_id")


def test_valid_restored_memory_exports(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    res = api.resume_persisted_repository(rid)
    assert res["ok"] is True
    export = api.session_export_packet()
    assert export.get("ok") is True
    assert "ATLAS_REPOSITORY_MEMORY v1" in export.get("text", "")


def test_tampered_memory_still_rejected(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem["text"] = "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO"
    mem_path.write_text(json.dumps(mem), encoding="utf-8")
    api._STATE.clear()
    api.resume_persisted_repository(rid)
    assert api.session_export_packet().get("ok") is False


def test_legacy_unsigned_memory_still_blocked(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem.pop("memory_hmac", None)
    mem_path.write_text(json.dumps(mem), encoding="utf-8")
    api._STATE.clear()
    api.resume_persisted_repository(rid)
    assert api._STATE.get("persistence_memory_rejected") is True
    assert api.session_export_packet().get("ok") is False


def _bundle_blob() -> bytes:
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    assert bundle["ok"] is True
    return base64.b64decode(bundle["content_base64"])


def test_support_bundle_redacts_persistence_secret_marker(data_dir, tmp_path, monkeypatch):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    persistence.load_persistence_secret(data_dir)
    log_path = Path(data_dir) / "launcher.log"
    log_path.write_text("persistence_secret\napi_key=LEAK\n", encoding="utf-8")
    blob = _bundle_blob().decode("utf-8", errors="replace")
    assert "persistence_secret" not in blob.lower()


def test_support_bundle_redacts_persistence_secret_path(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    log_path = Path(data_dir) / "launcher.log"
    log_path.write_text(
        "security/persistence_secret\nC:\\Users\\demo\\.atlas_desktop\\security\\persistence_secret\n",
        encoding="utf-8",
    )
    blob = _bundle_blob().decode("utf-8", errors="replace")
    assert "persistence_secret" not in blob.lower()
    assert "security/" not in blob or "[REDACTED]" in blob


def test_support_bundle_redacts_persistence_secret_case_variants(data_dir, tmp_path):
    _fresh()
    log_path = Path(data_dir) / "launcher.log"
    log_path.write_text(
        "PERSISTENCE_SECRET\nPersistence secret\npersistence_secret=abc123\n",
        encoding="utf-8",
    )
    blob = _bundle_blob().decode("utf-8", errors="replace").lower()
    assert "persistence_secret" not in blob
    assert "persistence secret" not in blob


def test_support_bundle_does_not_include_security_secret_file(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    secret = persistence.load_persistence_secret(data_dir)
    blob = _bundle_blob()
    assert secret not in blob
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = zf.namelist()
    assert not any("security" in name for name in names)
    assert not any("persistence_secret" in name for name in names)
