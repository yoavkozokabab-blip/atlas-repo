"""Phase 174B — trust integrity + targeted refresh regressions."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api
from atlas_desktop import repository_memory as rm
from atlas_desktop import trust_integrity as ti
from atlas_desktop.install_support import environment_status


def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update({
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
    })


def _tiny_repo(tmp_path: Path, dirname: str = "repo", files: dict | None = None) -> Path:
    root = tmp_path / dirname
    root.mkdir(exist_ok=True)
    for name, body in (files or {"a.py": "x = 1\n"}).items():
        (root / name).write_text(body, encoding="utf-8")
    return root


def _seed_build_plan(tmp_path, files: list[str] | None = None) -> Path:
    root = _tiny_repo(tmp_path, files={"a.py": "x = 1\n", "b.py": "y = 2\n"})
    _fresh_state()
    assert api.scan_repository(str(root))["ok"]
    rec = files or ["a.py"]
    with patch(
        "atlas_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "intent": "feature",
                "confidence": "medium",
                "files_to_inspect_first": rec,
                "files_likely_to_modify": rec,
            },
        },
    ):
        plan = api.plan_change("add logging")
    assert plan.get("ok") is True
    assert api._STATE.get("workflow_context")
    return root


@pytest.fixture
def tiny_scan(tmp_path):
    _fresh_state()
    root = _tiny_repo(tmp_path)
    scan = api.scan_repository(str(root))
    assert scan["ok"]
    return root, scan


def test_recommended_file_changed_targeted_refresh_available(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    (root / "a.py").write_text("x = 999\n", encoding="utf-8")

    status = api.trust_integrity_status()
    ts = status["trust_status"]
    assert ts.get("targeted_refresh_available") is True
    assert ts.get("repo_changed_outside_plan") is False
    assert "last Atlas plan changed" in (ts.get("message") or "")


def test_unrelated_file_changed_full_rescan_warning(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    (root / "b.py").write_text("y = 999\n", encoding="utf-8")

    status = api.trust_integrity_status()
    ts = status["trust_status"]
    assert ts.get("repo_changed_outside_plan") is True
    assert ts.get("targeted_refresh_available") is False
    assert "outside the last Atlas plan" in (ts.get("message") or "")


def test_export_blocked_while_stale(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    (root / "a.py").write_text("x = 999\n", encoding="utf-8")

    export = api.context_export()
    assert export.get("ok") is False
    assert "refresh before exporting" in (export.get("message") or "").lower()

    pkt = api.session_export_packet()
    assert pkt.get("ok") is False


def test_workflow_still_returns_historical_plan_when_stale(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    (root / "a.py").write_text("x = 999\n", encoding="utf-8")

    with patch(
        "atlas_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {"intent": "feature", "confidence": "medium", "files_to_inspect_first": ["a.py"]},
        },
    ):
        result = api.plan_change("add logging")
    assert result.get("ok") is True
    assert result.get("context_stale") is True
    assert result.get("export_blocked") is True
    assert "export" not in result


def test_targeted_refresh_clears_stale_for_recommended_files(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    (root / "a.py").write_text("x = 999\n", encoding="utf-8")
    assert api.trust_integrity_status()["trust_status"].get("fresh") is False

    refresh = api.refresh_changed_files()
    assert refresh.get("ok") is True
    assert "a.py" in (refresh.get("refreshed_files") or [])

    ts = api.trust_integrity_status()["trust_status"]
    assert ts.get("fresh") is True
    export = api.context_export()
    assert export.get("ok") is True


def test_no_automatic_full_rescan_on_file_change(tiny_scan):
    root, _ = tiny_scan
    scan_mock = MagicMock(side_effect=AssertionError("automatic full rescan must not run"))
    with patch.object(api, "scan_repository", scan_mock):
        (root / "a.py").write_text("x = 999\n", encoding="utf-8")
        api.context_export()
        api.trust_integrity_status()
    scan_mock.assert_not_called()


def test_memory_refresh_generation_increments_after_targeted_refresh(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    before = int(api._STATE.get("refresh_generation") or 0)
    (root / "a.py").write_text("x = 888\n", encoding="utf-8")
    refresh = api.refresh_changed_files()
    assert refresh.get("ok") is True
    assert int(api._STATE.get("refresh_generation") or 0) == before + 1
    mem = api._STATE.get("_current_memory") or {}
    assert int(mem.get("refresh_generation") or 0) == before + 1


def test_old_memory_ref_rejected_after_refresh(tmp_path):
    root = _seed_build_plan(tmp_path, ["a.py"])
    old_ref = api._STATE["workflow_context"]["memory_ref"]
    (root / "a.py").write_text("x = 777\n", encoding="utf-8")
    assert api.refresh_changed_files().get("ok") is True
    new_ref = api._STATE.get("active_memory_ref")
    assert new_ref
    if new_ref == old_ref:
        api._STATE["active_memory_ref"] = "refreshed-new-id"
        new_ref = "refreshed-new-id"

    api._STATE["workflow_context"]["memory_ref"] = old_ref
    export = api.context_export()
    assert export.get("ok") is False
    assert export.get("status") == "memory_ref_stale"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_head_change_requires_full_rescan(tmp_path):
    root = tmp_path / "gitrepo"
    root.mkdir()
    (root / "main.py").write_text("x = 1\n", encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True, env=env)

    _fresh_state()
    assert api.scan_repository(str(root))["ok"]
    (root / "main.py").write_text("x = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(["git", "commit", "-m", "second"], cwd=root, check=True, capture_output=True, env=env)

    export = api.context_export()
    assert export.get("ok") is False
    assert api.trust_integrity_status()["trust_status"].get("repo_changed_outside_plan") is True


def test_memory_file_tamper_discarded_on_load(tiny_scan, tmp_path):
    root, _ = tiny_scan
    data_dir = str(tmp_path / "data")
    rm.update_after_scan(api._STATE, data_dir, generated_by_version="test")
    mem_path = rm._memory_path(str(root), data_dir)
    with open(mem_path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["modules"] = 99999
    data["memory_hash"] = "deadbeef"
    with open(mem_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    assert rm.load(str(root), data_dir) is None


def test_memory_tamper_in_state_export_refuses(tiny_scan):
    mem = api._STATE.get("_current_memory")
    assert mem
    mem["modules"] = 424242
    export = api.session_export_packet()
    assert export.get("ok") is False
    assert export.get("status") == "memory_invalid"


def test_memory_write_failure_status_exposed(tiny_scan, tmp_path):
    with patch.object(rm, "persist", return_value=("", False, "Permission denied")):
        pkt = rm.update_after_scan(api._STATE, str(tmp_path / "memfail"), generated_by_version="test")
    assert api._STATE.get("memory_persistence_status") == "failed"
    assert pkt.get("persistent_memory_available") is False


def test_repo_path_switch_stale_memory_not_exported(tmp_path):
    _fresh_state()
    root_a = _tiny_repo(tmp_path, "repo_a", {"a.py": "x = 1\n"})
    root_b = _tiny_repo(tmp_path, "repo_b", {"b.py": "y = 2\n"})
    assert api.scan_repository(str(root_a))["ok"]
    api.select_repository(str(root_b))
    assert api.session_export_packet().get("ok") is False


def test_weak_graph_build_refuses_without_exact_evidence(tiny_scan):
    api._STATE["scan"]["graph_health"] = {"label": "unsupported_language_limited"}
    with patch(
        "atlas_desktop.planning_engine.plan_change",
        return_value={"ok": True, "plan": {"intent": "f", "files_to_inspect_first": []}},
    ):
        result = api.plan_change("add logging")
    assert result.get("ok") is False
    assert result.get("status") == "unsupported_language_limited"


def test_concurrent_select_and_export_no_wrong_repo_memory(tmp_path):
    _fresh_state()
    root_a = _tiny_repo(tmp_path, "repo_a", {"a.py": "x = 1\n"})
    root_b = _tiny_repo(tmp_path, "repo_b", {"b.py": "y = 2\n"})
    assert api.scan_repository(str(root_a))["ok"]
    mismatches: list[tuple[str, str]] = []
    barrier = threading.Barrier(2)
    # Loops honor this flag so the threads ALWAYS terminate before the test
    # returns — a join(timeout=...) alone leaks a still-running scan thread
    # into every later test module under CPU load (order-dependent failures).
    stop = threading.Event()

    def flip_paths() -> None:
        barrier.wait()
        for _ in range(30):
            if stop.is_set():
                return
            api.select_repository(str(root_b))
            api.select_repository(str(root_a))
            api.scan_repository(str(root_a))

    def export_loop() -> None:
        barrier.wait()
        for _ in range(30):
            if stop.is_set():
                return
            pkt = api.session_export_packet()
            if not pkt.get("ok"):
                continue
            path = os.path.abspath(str(api._STATE.get("path") or ""))
            scan_path = os.path.abspath(str((api._STATE.get("scan") or {}).get("repo_path") or path))
            if path != scan_path:
                mismatches.append((path, scan_path))

    t1 = threading.Thread(target=flip_paths)
    t2 = threading.Thread(target=export_loop)
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    stop.set()
    t1.join(timeout=120)
    t2.join(timeout=120)
    assert not t1.is_alive() and not t2.is_alive(), "race threads must not outlive the test"
    assert not mismatches


def test_support_diagnostics_include_trust_integrity(tiny_scan):
    diag = api.beta_diagnostics()
    assert "trust_integrity" in diag
    assert "targeted_refresh_available" in diag["trust_integrity"]
    env = environment_status()
    assert "trust_integrity" in env


def test_signature_v2_uses_index_manifest_not_arbitrary_cap(tmp_path):
    root = _tiny_repo(tmp_path, "wide", {"aaa.py": "a = 1\n", "zzz.py": "z = 1\n"})
    _fresh_state()
    assert api.scan_repository(str(root))["ok"]
    sig_before = api._STATE["scan"]["signature_v2"]["signature"]
    (root / "zzz.py").write_text("z = 999\n", encoding="utf-8")
    live = ti.compute_signature_v2(
        str(root), {"mode": "entire_repo"},
        indexed_files=api._STATE["index"]["files"], include_content_hash=True,
    )
    assert live["signature"] != sig_before
