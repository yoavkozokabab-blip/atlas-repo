"""Phase 181B — scan and workflow history persistence."""

from __future__ import annotations

import json
import os
import sys
import time
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
    (repo / "util.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    return str(repo)


def test_scan_state_written_after_scan(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    latest = Path(data_dir) / "scans" / rid / "latest.json"
    assert latest.is_file()
    record = json.loads(latest.read_text(encoding="utf-8"))
    assert record["repo_path"] == os.path.abspath(repo)
    assert record["file_count"] >= 1
    assert record["scan_signature"]
    assert not persistence.persistence_files_contain_source(data_dir)


def test_valid_scan_restored_after_simulated_restart(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    rid = rm.repo_id(repo)
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    status = api.bootstrap_persistence(auto_restore=True)
    assert status.get("restored") is True
    assert api._STATE.get("scan")
    assert api._STATE.get("graph")
    assert rm.repo_id(str(api._STATE.get("path"))) == rid


def test_changed_file_marks_scan_stale(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    bundle = persistence.load_scan_state(data_dir, rm.repo_id(repo))
    assert bundle
    validation = persistence.validate_scan_state(bundle["record"], repo)
    assert validation["status"] == "valid"
    app_py = Path(repo) / "app.py"
    app_py.write_text(app_py.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8")
    stale = persistence.validate_scan_state(bundle["record"], repo)
    assert stale["status"] == "stale"


def test_wrong_repo_path_refuses_restore(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    bundle = persistence.load_scan_state(data_dir, rm.repo_id(repo))
    other = str(tmp_path / "other")
    os.makedirs(other, exist_ok=True)
    wrong = persistence.validate_scan_state(bundle["record"], other)
    assert wrong["status"] == "wrong_repo"
    api._STATE.clear()
    _, ok_res = server.dispatch("POST", "/api/repositories/resume", {"repo_id": rm.repo_id(repo)})
    assert ok_res["ok"] is True


def test_history_saved_for_build_investigate_impact(data_dir, tmp_path):
    _fresh()
    api.load_demo_mode("small")
    build = api.plan_change("Improve error handling in core/hub.py")
    assert build.get("ok")
    inv = api.investigate_symptom("API requests fail intermittently under load")
    assert inv.get("ok")
    imp = api.change_impact_simulation("core/hub.py")
    assert imp.get("ok")
    rid = rm.repo_id(str(api._STATE.get("path")))
    for wf in ("build", "investigate", "impact"):
        rows = persistence.list_workflow_history(data_dir, rid, wf)
        assert rows, f"missing history for {wf}"


def test_history_survives_restart(data_dir, tmp_path):
    _fresh()
    api.load_demo_mode("small")
    api.plan_change("Improve error handling in core/hub.py")
    rid = rm.repo_id(str(api._STATE.get("path")))
    rows = persistence.list_workflow_history(data_dir, rid, "build")
    hid = rows[0]["history_id"]
    api._STATE.clear()
    item = persistence.get_workflow_history_item(data_dir, hid, state=None)
    assert item and item["history_id"] == hid


def test_stale_history_cannot_export(data_dir, tmp_path):
    _fresh()
    repo = _mini_repo(tmp_path)
    api.scan_repository(repo)
    api.plan_change("Add logging to app.py")
    rid = rm.repo_id(repo)
    rows = persistence.list_workflow_history(data_dir, rid, "build")
    hid = rows[0]["history_id"]
    Path(repo, "app.py").write_text("def main():\n    return 99\n", encoding="utf-8")
    api._STATE["scan"]["scan_id"] = "stale-scan-id"
    item = persistence.get_workflow_history_item(data_dir, hid, state=api._STATE)
    assert item.get("export_allowed") is False


def test_cleanup_removes_old_records(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "MAX_SCANS", 2)
    reg = {"scans": []}
    for i in range(4):
        rid = f"deadbeef{i:08d}"[:16]
        persistence._scan_dir(data_dir, rid)
        record = {
            "repo_id": rid,
            "repo_path": str(tmp_path / f"r{i}"),
            "repo_name": f"r{i}",
            "created_at": f"2026-01-0{i+1}T00:00:00Z",
            "file_count": 1,
            "module_count": 1,
            "graph_health_label": "healthy",
            "scan_signature": f"sig{i}",
        }
        persistence._json_write(os.path.join(persistence._scan_dir(data_dir, rid), "latest.json"), record)
        reg["scans"].append({
            "repo_id": rid,
            "repo_path": record["repo_path"],
            "repo_name": record["repo_name"],
            "last_scan_at": record["created_at"],
            "file_count": 1,
            "module_count": 1,
            "graph_health": "healthy",
        })
    persistence._json_write(persistence._registry_path(data_dir), reg)
    result = persistence.cleanup_old_scans(data_dir)
    assert len(result.get("removed_scans") or []) >= 2
    remaining = json.loads(Path(persistence._registry_path(data_dir)).read_text(encoding="utf-8"))
    assert len(remaining["scans"]) <= 2


def test_recent_repos_api_returns_backend_data(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    _, recent = server.dispatch("GET", "/api/repositories/recent")
    assert recent["ok"] is True
    assert len(recent["items"]) >= 1
    assert recent["items"][0].get("repo_name")
    assert recent["items"][0].get("file_count") is not None


def test_no_raw_source_content_in_persistence_files(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_mini_repo(tmp_path))
    for root, _dirs, files in os.walk(Path(data_dir) / "scans"):
        for name in files:
            if not name.endswith(".json"):
                continue
            blob = Path(root, name).read_text(encoding="utf-8")
            assert "def main():" not in blob
            assert blob.count('"text"') < 2
