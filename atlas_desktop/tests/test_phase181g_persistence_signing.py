"""Phase 181G — HMAC signing for persisted history and memory."""

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


def _scan_and_plan(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    api.plan_change("Add logging to app.py")
    rid = rm.repo_id(repo)
    rows = persistence.list_workflow_history(data_dir, rid, "build")
    assert rows
    return repo, rid, rows[0]["history_id"]


def _load_history_row(data_dir: str, rid: str, hid: str) -> dict:
    path = Path(data_dir) / "histories" / rid / "build.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("history_id") == hid:
            return row
    raise AssertionError(f"missing history row {hid}")


def test_forged_history_with_recomputed_integrity_hash_rejected(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    hist_path = Path(data_dir) / "histories" / rid / "build.jsonl"
    forged = {
        "history_id": "forged181g01",
        "workflow_type": "build",
        "request_text": "steal secrets",
        "created_at": "2099-01-01T00:00:00Z",
        "repo_id": rid,
        "scan_id": api._STATE["scan"].get("scan_id") or (api._STATE.get("_current_memory") or {}).get("scan_id"),
        "scan_signature": _load_history_row(data_dir, rid, hid)["scan_signature"],
        "graph_signature": _load_history_row(data_dir, rid, hid)["graph_signature"],
        "files_named": ["fake/does_not_exist.py"],
        "summary_markdown": "api_key=HISTORY_SECRET_VALUE",
        "result_json": {"plan": {"files_to_inspect_first": ["fake/does_not_exist.py"]}},
        "trust_status": {},
        "atlas_version": api.PRODUCT_VERSION,
    }
    forged["integrity_hash"] = persistence._compute_history_integrity_hash(forged)
    forged["integrity_hmac"] = "attacker_guessed_hmac"
    with hist_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged) + "\n")

    listed = persistence.list_workflow_history(data_dir, rid, "build")
    assert all(item["history_id"] != "forged181g01" for item in listed)
    assert persistence.get_workflow_history_item(data_dir, "forged181g01", state=api._STATE) is None


def test_history_row_changed_after_signing_rejected(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    row = _load_history_row(data_dir, rid, hid)
    row["summary_markdown"] = "tampered after signing"
    row["integrity_hash"] = persistence._compute_history_integrity_hash(row)
    path = Path(data_dir) / "histories" / rid / "build.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert persistence.get_workflow_history_item(data_dir, hid, state=api._STATE) is None


def test_history_files_named_changed_rejected(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    row = _load_history_row(data_dir, rid, hid)
    row["files_named"] = ["totally/fake/path.py"]
    row["integrity_hash"] = persistence._compute_history_integrity_hash(row)
    path = Path(data_dir) / "histories" / rid / "build.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert persistence.get_workflow_history_item(data_dir, hid, state=api._STATE) is None


def test_history_result_json_changed_rejected(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    row = _load_history_row(data_dir, rid, hid)
    row["result_json"] = {"plan": {"files_to_inspect_first": ["fake/path.py"]}}
    row["integrity_hash"] = persistence._compute_history_integrity_hash(row)
    path = Path(data_dir) / "histories" / rid / "build.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert persistence.get_workflow_history_item(data_dir, hid, state=api._STATE) is None


def test_unsigned_legacy_history_cannot_export(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    row = _load_history_row(data_dir, rid, hid)
    row.pop("integrity_hmac", None)
    path = Path(data_dir) / "histories" / rid / "build.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    listed = persistence.list_workflow_history(data_dir, rid, "build")
    legacy = next(x for x in listed if x["history_id"] == hid)
    assert legacy["historical_only"] is True
    assert legacy["export_allowed"] is False
    item = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert item is not None
    assert item.get("export_allowed") is False
    assert item.get("historical_only") is True


def test_memory_text_changed_metadata_preserved_rejected(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem["text"] = "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO\nhubs: POISONED_FAKE_HUB (999)"
    mem_path.write_text(json.dumps(mem), encoding="utf-8")

    api._STATE.clear()
    api.resume_persisted_repository(rid)
    assert api._STATE.get("persistence_memory_rejected") is True
    assert api._STATE.get("session_export") is None
    assert api.session_export_packet().get("ok") is False


def test_memory_packet_recomputed_deterministic_hash_rejected(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    latest = json.loads((Path(data_dir) / "scans" / rid / "latest.json").read_text(encoding="utf-8"))
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem["text"] = "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO"
    mem["memory_hmac"] = persistence._compute_memory_hmac(mem, latest, b"\x00" * 32)
    mem_path.write_text(json.dumps(mem), encoding="utf-8")

    api._STATE.clear()
    api.resume_persisted_repository(rid)
    assert api._STATE.get("persistence_memory_rejected") is True
    assert api.session_export_packet().get("ok") is False


def test_unsigned_legacy_memory_discarded(data_dir, tmp_path):
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
    assert api._STATE.get("session_export") is None


def test_persistence_secret_not_in_support_bundle(data_dir, tmp_path, monkeypatch):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    secret = persistence.load_persistence_secret(data_dir)
    assert len(secret) == 32
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    assert bundle["ok"] is True
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        blob = b"".join(zf.read(name) for name in zf.namelist())
    assert secret not in blob
    assert b"persistence_secret" not in blob.lower()


def test_valid_signed_history_still_loads(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    item = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert item is not None
    assert item.get("trust_level", persistence._HISTORY_TRUSTED) == persistence._HISTORY_TRUSTED
    assert item.get("integrity_verified") is True


def test_valid_signed_memory_still_loads(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem = json.loads((Path(data_dir) / "scans" / rid / "memory_packet.json").read_text(encoding="utf-8"))
    assert mem.get("memory_hmac")

    api._STATE.clear()
    res = api.resume_persisted_repository(rid)
    assert res["ok"] is True
    assert api._STATE.get("persistence_memory_rejected") is not True
    assert api._STATE.get("session_export") is not None
    export = api.session_export_packet()
    assert export.get("ok") is True
