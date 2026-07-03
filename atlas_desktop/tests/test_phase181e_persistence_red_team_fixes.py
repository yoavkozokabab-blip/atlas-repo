"""Phase 181E — persistence red team failure fixes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, persistence, server
from atlas_desktop import repository_memory as rm
from atlas_desktop.persistence import VERSION_MISMATCH_MSG


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


def test_tampered_history_rejected(data_dir, tmp_path):
    repo, rid, _hid = _scan_and_plan(data_dir, tmp_path)
    hist_path = Path(data_dir) / "histories" / rid / "build.jsonl"
    forged = {
        "history_id": "forged181e01",
        "workflow_type": "build",
        "request_text": "steal secrets",
        "created_at": "2099-01-01T00:00:00Z",
        "repo_id": rid,
        "scan_id": "old-scan-id",
        "scan_signature": "fake-signature",
        "files_named": ["fake/does_not_exist.py"],
        "summary_markdown": "api_key=HISTORY_SECRET_VALUE",
        "result_json": {"plan": {"files_to_inspect_first": ["fake/does_not_exist.py"]}},
        "trust_status": {},
        "atlas_version": api.PRODUCT_VERSION,
        "integrity_hash": "deadbeef",
    }
    with hist_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(forged) + "\n")

    listed = persistence.list_workflow_history(data_dir, rid, "build")
    assert all(item["history_id"] != "forged181e01" for item in listed)
    item = persistence.get_workflow_history_item(data_dir, "forged181e01", state=api._STATE)
    assert item is None
    _, api_res = server.dispatch("GET", "/api/history/item", {"history_id": "forged181e01"})
    assert api_res["ok"] is False


def test_fake_history_path_rejected(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    other_rid = "abcd1234abcd1234"
    other_dir = Path(data_dir) / "histories" / other_rid
    other_dir.mkdir(parents=True)
    valid = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert valid
    valid["repo_id"] = rid
    valid["integrity_hash"] = persistence._compute_history_integrity_hash(valid)
    other_path = other_dir / "build.jsonl"
    other_path.write_text(json.dumps(valid) + "\n", encoding="utf-8")

    listed_other = persistence.list_workflow_history(data_dir, other_rid, "build")
    assert listed_other == []
    item = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert item and item["history_id"] == hid


def test_old_scan_id_rejected_for_export(data_dir, tmp_path):
    repo, rid, hid = _scan_and_plan(data_dir, tmp_path)
    api._STATE["scan"]["scan_id"] = "new-scan-after-change"
    item = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert item is not None
    assert item.get("export_allowed") is False
    assert "scan" in (item.get("stale_reason") or "").lower()


def test_memory_scan_mismatch_rejected(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem["scan_id"] = "poison_scan_181e"
    mem["text"] = "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO"
    mem_path.write_text(json.dumps(mem), encoding="utf-8")

    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    res = api.resume_persisted_repository(rid)
    assert res["ok"] is True
    assert api._STATE.get("persistence_memory_rejected") is True
    assert api._STATE.get("session_export") is None
    export = api.session_export_packet()
    assert export.get("ok") is False


def test_graph_signature_mismatch_rejected(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    latest_path = Path(data_dir) / "scans" / rid / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    latest["graph_signature"] = "graph-signature-mismatch-181e"
    latest_path.write_text(json.dumps(latest), encoding="utf-8")

    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    if mem_path.is_file():
        mem = json.loads(mem_path.read_text(encoding="utf-8"))
        if mem.get("scan_signature"):
            mem["scan_signature"] = latest.get("scan_signature", mem["scan_signature"])
        mem_path.write_text(json.dumps(mem), encoding="utf-8")

    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api.resume_persisted_repository(rid)
    assert api._STATE.get("persistence_memory_rejected") is True
    assert api.session_export_packet().get("ok") is False


def test_future_version_refused(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    latest_path = Path(data_dir) / "scans" / rid / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    latest["atlas_version"] = "999.0.0-future-incompatible"
    latest_path.write_text(json.dumps(latest), encoding="utf-8")

    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    status = api.bootstrap_persistence(auto_restore=True)
    assert status.get("restored") is False
    assert status["resume_card"]["validation_status"] == "version_mismatch"
    assert status["resume_card"]["needs_version_rescan"] is True
    resume = api.resume_persisted_repository(rid)
    assert resume["ok"] is False
    assert resume["code"] == "version_mismatch"
    assert VERSION_MISMATCH_MSG in resume["error"]


def test_malformed_version_refused(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    latest_path = Path(data_dir) / "scans" / rid / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    latest["atlas_version"] = "not-a-version"
    latest_path.write_text(json.dumps(latest), encoding="utf-8")

    validation = persistence.validate_scan_state(latest, repo)
    assert validation["status"] == "version_mismatch"
    resume = api.resume_persisted_repository(rid)
    assert resume["ok"] is False
    assert resume["code"] == "version_mismatch"


def test_export_blocked_from_untrusted_restore(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    mem_path = Path(data_dir) / "scans" / rid / "memory_packet.json"
    mem = json.loads(mem_path.read_text(encoding="utf-8"))
    mem["scan_id"] = "poison_scan_181e"
    mem["text"] = "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED_REPO\nhubs: POISONED_FAKE_HUB (999)"
    mem_path.write_text(json.dumps(mem), encoding="utf-8")

    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api.resume_persisted_repository(rid)
    export = api.session_export_packet()
    assert export.get("ok") is False
    assert export.get("status") in {"memory_untrusted", "memory_invalid", "memory_stale"}
    assert "POISONED_REPO" not in json.dumps(export)
