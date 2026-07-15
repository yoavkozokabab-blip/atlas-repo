"""Installed-runtime persistence root, migration, and installer preservation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from atlas_desktop import (
    api,
    data_paths,
    install_support,
    persistence,
    persistence_migration,
)
from atlas_desktop import repository_memory as repository_memory

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "packaging" / "installer" / "Atlas.iss"


def _fresh_state() -> None:
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "last_scope": {"mode": "entire_repo"},
            "scan_cache": {},
            "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
            "session_export": None,
            "repository_memory": None,
            "_current_memory": None,
        }
    )


def _mini_repo(parent: Path, name: str = "fixture_repo") -> Path:
    repo = parent / name
    repo.mkdir()
    (repo / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    (repo / "model.py").write_text(
        "from app import answer\nVALUE = answer()\n", encoding="utf-8"
    )
    return repo


def _scan_into(root: Path, repo: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(root))
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()
    result = api.scan_repository(str(repo))
    assert result["ok"] is True
    rid = repository_memory.repo_id(str(repo))
    assert (root / "scans" / rid / "latest.json").is_file()
    return rid


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_canonical_root_is_per_user_and_cwd_exe_port_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "interactive-user"
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.setenv("HOME", str(tmp_path / "different-home"))
    monkeypatch.delenv("ATLAS_DESKTOP_DATA", raising=False)
    monkeypatch.delenv("JARVIS_DESKTOP_DATA", raising=False)
    expected = profile / ".atlas_desktop"
    assert Path(data_paths.canonical_desktop_data_dir()) == expected
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ATLAS_PORT", "65001")
    assert Path(data_paths.canonical_desktop_data_dir()) == expected


def test_existing_registry_and_scan_artifacts_survive_in_place_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "historical"
    canonical = tmp_path / "canonical"
    repo = _mini_repo(tmp_path)
    rid = _scan_into(source, repo, monkeypatch)
    first = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)], force=True
    )
    assert first["status"] == "migrated"
    registry = canonical / "scans" / "registry.json"
    artifacts = canonical / "scans" / rid
    before = {path.name: _sha(path) for path in artifacts.iterdir() if path.is_file()}
    registry_before = _sha(registry)
    second = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)], force=True
    )
    assert second["migrated_repo_ids"] == []
    assert _sha(registry) == registry_before
    assert {path.name: _sha(path) for path in artifacts.iterdir() if path.is_file()} == before


def test_fresh_installed_launch_discovers_recent_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "legacy"
    canonical = tmp_path / "canonical"
    repo = _mini_repo(tmp_path)
    rid = _scan_into(source, repo, monkeypatch)
    migrated = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    assert migrated["migrated_repo_ids"] == [rid]
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(canonical))
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()
    status = api.bootstrap_persistence(auto_restore=True)
    assert status["restored"] is True
    assert api._STATE["path"] == str(repo)
    assert len(persistence.list_registry_rows(str(canonical))) == 1


def test_read_only_persistence_probe_does_not_block_later_auto_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "legacy"
    canonical = tmp_path / "canonical"
    repo = _mini_repo(tmp_path)
    rid = _scan_into(source, repo, monkeypatch)
    migrated = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    assert migrated["migrated_repo_ids"] == [rid]
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(canonical))
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()

    preview = api.bootstrap_persistence(auto_restore=False)
    assert preview["restored"] is False
    assert preview["resume_card"]["can_resume"] is True
    assert api._STATE.get("scan") is None

    restored = api.bootstrap_persistence(auto_restore=True)
    assert restored["restored"] is True
    assert api._STATE["path"] == str(repo)
    assert repository_memory.repo_id(api._STATE["path"]) == rid


def test_installer_never_resolves_or_deletes_elevated_user_data() -> None:
    script = INSTALLER.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in script
    assert "[UninstallDelete]" not in script
    files_section = script.split("[Files]", 1)[1].split("[Icons]", 1)[0]
    assert ".atlas_desktop" not in files_section
    assert "desktop_data" not in files_section
    assert r'Source: "staging\*"' in files_section


def test_clean_install_without_registry_is_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "clean-user" / ".atlas_desktop"
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(canonical))
    data_paths.reset_desktop_data_dir_cache()
    _fresh_state()
    status = api.bootstrap_persistence(auto_restore=True)
    assert status["restored"] is False
    assert not (canonical / "scans" / "registry.json").exists()
    assert persistence.list_registry_rows(str(canonical)) == []


def test_update_with_valid_registry_restores_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "user-data"
    repo = _mini_repo(tmp_path)
    rid = _scan_into(canonical, repo, monkeypatch)
    _fresh_state()
    status = api.bootstrap_persistence(auto_restore=True)
    assert status["restored"] is True
    assert repository_memory.repo_id(api._STATE["path"]) == rid
    assert api._STATE["scan"]["file_count"] == 2


def test_invalid_registry_fails_safe_without_deleting_source_or_backup(
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid"
    canonical = tmp_path / "canonical"
    (source / "scans").mkdir(parents=True)
    registry = source / "scans" / "registry.json"
    registry.write_text("{not-json", encoding="utf-8")
    backup = source / "scans" / "registry.pre_cleanup.json"
    backup.write_text('{"scans":[]}\n', encoding="utf-8")
    before = (_sha(registry), _sha(backup))
    result = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    assert result["status"] == "no_valid_state"
    assert (_sha(registry), _sha(backup)) == before
    assert not (canonical / "scans" / "registry.json").exists()


def test_moved_repository_is_recorded_as_recoverable_path_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    canonical = tmp_path / "canonical"
    repo = _mini_repo(tmp_path)
    rid = _scan_into(source, repo, monkeypatch)
    moved = tmp_path / "moved-repository"
    repo.rename(moved)
    result = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    entry = result["sources"][0]["entries"][0]
    assert entry["repo_id"] == rid
    assert entry["status"] == "path_missing"
    assert entry["repo_path_exists"] is False
    assert (source / "scans" / rid / "latest.json").is_file()


def test_registry_migration_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    canonical = tmp_path / "canonical"
    repo = _mini_repo(tmp_path)
    _scan_into(source, repo, monkeypatch)
    first = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    registry_hash = _sha(canonical / "scans" / "registry.json")
    second = persistence_migration.migrate_repository_state(
        canonical_root=str(canonical), source_roots=[str(source)]
    )
    assert first["status"] == "migrated"
    assert second["idempotent_reuse"] is True
    assert _sha(canonical / "scans" / "registry.json") == registry_hash


def test_ui_distinguishes_configured_agent_without_repository_context() -> None:
    shell = (ROOT / "atlas_desktop" / "static" / "desktop-shell.js").read_text(
        encoding="utf-8"
    )
    workbench = (ROOT / "atlas_desktop" / "static" / "workbench-v3.js").read_text(
        encoding="utf-8"
    )
    assert "Configured — select a repository" in shell
    assert "Configured — select a repository" in workbench
    assert "Configured; repository context ready" in workbench
    assert 'summary?.ok ? "Connected"' not in workbench
    assert '"Connected agents"' not in workbench


def test_installer_staging_has_no_user_registry_payload() -> None:
    staging = ROOT / "packaging" / "installer" / "staging"
    if not staging.exists():
        pytest.skip("staging is generated only during packaging")
    forbidden = [
        path
        for path in staging.rglob("*")
        if path.is_file()
        and (
            path.name.lower() == "registry.json"
            or ".atlas_desktop" in str(path).lower()
            or "accounts_state.json" in str(path).lower()
        )
    ]
    assert forbidden == []


def test_persistence_diagnostics_reuses_one_live_staleness_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    status = {
        "fresh": True,
        "status": "fresh",
        "live_signature": "live-signature",
        "changed_files": [],
        "targeted_refresh_available": False,
        "repo_changed_outside_plan": False,
    }

    def _assess(_state):
        calls.append("assess")
        return status

    monkeypatch.setattr(api._ti, "assess_staleness", _assess)
    result = api.beta_diagnostics()
    assert calls == ["assess"]
    assert result["trust_integrity"]["live_signature"] == "live-signature"
    assert result["trust_integrity"]["scan_stale"] is False


def test_startup_status_reuses_one_persistence_identity_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    status = {
        "fresh": True,
        "status": "fresh",
        "live_signature": "live-signature",
        "changed_files": [],
        "targeted_refresh_available": False,
        "repo_changed_outside_plan": False,
    }

    def _assess(_state):
        calls.append("assess")
        return status

    monkeypatch.setattr(api._ti, "assess_staleness", _assess)
    result = install_support.environment_status()
    assert calls == ["assess"]
    assert result["diagnostics"]["trust_integrity"]["live_signature"] == "live-signature"
