from __future__ import annotations

import os

from atlas_desktop import api, data_paths, persistence, trust_integrity


def _reset_state():
    api._STATE.clear()
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "scan_cache": {},
            "session_export": None,
            "repository_memory": None,
            "_current_memory": None,
            "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
            "last_scope": {"mode": "entire_repo"},
        }
    )
    api._PERSISTENCE_BOOTSTRAPPED = False


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
    return root


def test_unchanged_signed_repository_restores_and_assesses_fresh(tmp_path, monkeypatch):
    data_dir = tmp_path / "atlas-data"
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(data_dir))
    data_paths.reset_desktop_data_dir_cache()
    _reset_state()
    root = _repo(tmp_path)
    assert api.scan_repository(str(root))["ok"]
    repo_id = persistence._repo_memory.repo_id(str(root))
    record = persistence.load_scan_state(str(data_dir), repo_id)["record"]
    assert persistence.validate_scan_state(record, str(root))["status"] == "valid"
    assert trust_integrity.assess_staleness(api._STATE)["status"] == "fresh"


def test_timestamp_only_change_does_not_poison_content_signature(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path / "atlas-data"))
    data_paths.reset_desktop_data_dir_cache()
    _reset_state()
    root = _repo(tmp_path)
    assert api.scan_repository(str(root))["ok"]
    target = root / "app" / "main.py"
    stat = target.stat()
    os.utime(target, (stat.st_atime + 5, stat.st_mtime + 5))
    status = trust_integrity.assess_staleness(api._STATE)
    assert status["status"] == "fresh"


def test_known_generated_installer_output_is_ignored_but_source_change_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path / "atlas-data"))
    data_paths.reset_desktop_data_dir_cache()
    _reset_state()
    root = _repo(tmp_path)
    assert api.scan_repository(str(root))["ok"]
    generated = root / "packaging" / "installer" / "output" / "Atlas_Setup.exe"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"generated payload")
    assert trust_integrity.assess_staleness(api._STATE)["status"] == "fresh"
    (root / "app" / "main.py").write_text("VALUE = 2\n", encoding="utf-8")
    status = trust_integrity.assess_staleness(api._STATE)
    assert status["status"] == "stale_outside_plan"
    assert status["changed_files"] == ["app/main.py"]


def test_v3_record_remains_valid_across_silent_update(tmp_path):
    root = _repo(tmp_path)
    scope = {"mode": "entire_repo"}
    legacy = trust_integrity.compute_signature_v2(
        str(root), scope, include_content_hash=True, signature_version=3
    )
    record = {
        "repo_path": str(root),
        "atlas_version": api.PRODUCT_VERSION,
        "scan_signature": legacy["signature"],
        "scope": scope,
    }
    validation = persistence.validate_scan_state(record, str(root))
    assert validation["status"] == "valid"
