"""Phase 174B — trust integrity P0 regressions.

Covers stale signatures, poisoned memory, persistence failures, weak-graph
refusals, concurrent state races, and support diagnostics exposure.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api
from jarvis_desktop import repository_memory as rm
from jarvis_desktop import trust_integrity as ti
from jarvis_desktop.install_support import environment_status


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


def _tiny_repo(tmp_path: Path, dirname: str = "repo", name: str = "a.py", body: str = "x = 1\n") -> Path:
    root = tmp_path / dirname
    root.mkdir(exist_ok=True)
    (root / name).write_text(body, encoding="utf-8")
    return root


@pytest.fixture
def tiny_scan(tmp_path):
    _fresh_state()
    root = _tiny_repo(tmp_path)
    scan = api.scan_repository(str(root))
    assert scan["ok"]
    return root, scan


def test_edit_after_scan_export_refuses_stale_scan(tiny_scan):
    root, _ = tiny_scan
    before = api.context_export()
    assert before.get("ok") is True

    (root / "a.py").write_text("x = 999\n", encoding="utf-8")
    after = api.context_export()
    assert after.get("ok") is False
    assert after.get("status") == "stale_scan"
    assert "fresh scan" in (after.get("message") or "").lower()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_head_change_export_refuses(tmp_path):
    root = tmp_path / "gitrepo"
    root.mkdir()
    (root / "main.py").write_text("x = 1\n", encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.com"}
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=root, check=True, capture_output=True, env=env,
    )

    _fresh_state()
    scan = api.scan_repository(str(root))
    assert scan["ok"]

    (root / "main.py").write_text("x = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=root, check=True, capture_output=True, env=env,
    )

    export = api.context_export()
    assert export.get("ok") is False
    assert export.get("status") == "stale_git_head_changed"


def test_memory_file_tamper_discarded_on_load(tiny_scan, tmp_path, monkeypatch):
    root, _ = tiny_scan
    data_dir = str(tmp_path / "data")
    rm.update_after_scan(api._STATE, data_dir, generated_by_version="test")

    mem_path = rm._memory_path(str(root), data_dir)
    assert os.path.isfile(mem_path)
    with open(mem_path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["modules"] = 99999
    data["memory_hash"] = "deadbeef"
    with open(mem_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)

    loaded = rm.load(str(root), data_dir)
    assert loaded is None


def test_memory_tamper_in_state_export_refuses(tiny_scan):
    root, _ = tiny_scan
    mem = api._STATE.get("_current_memory")
    assert mem
    mem["modules"] = 424242
    export = api.session_export_packet()
    assert export.get("ok") is False
    assert export.get("status") == "memory_invalid"


def test_memory_write_failure_status_exposed(tiny_scan, tmp_path):
    root, _ = tiny_scan
    data_dir = str(tmp_path / "memfail")

    with patch.object(rm, "persist", return_value=("", False, "Permission denied")):
        pkt = rm.update_after_scan(
            api._STATE, data_dir, generated_by_version="phase174b-test"
        )

    assert api._STATE.get("memory_persistence_status") == "failed"
    assert "Permission denied" in (api._STATE.get("memory_persistence_error") or "")
    assert pkt.get("memory_persistence_status") == "failed"
    assert pkt.get("persistent_memory_available") is False


def test_repo_path_switch_stale_memory_not_exported(tmp_path):
    _fresh_state()
    root_a = _tiny_repo(tmp_path, "repo_a", "a.py", "x = 1\n")
    root_b = _tiny_repo(tmp_path, "repo_b", "b.py", "y = 2\n")
    assert api.scan_repository(str(root_a))["ok"]

    sel = api.select_repository(str(root_b))
    assert sel["ok"]
    assert sel.get("requires_rescan") is True
    assert api._STATE.get("session_export") is None
    assert api._STATE.get("_current_memory") is None

    export = api.session_export_packet()
    assert export.get("ok") is False
    assert export.get("status") in ("requires_rescan", "stale_scan")


def test_weak_graph_build_refuses_without_exact_evidence(tiny_scan):
    _, _ = tiny_scan
    api._STATE["scan"]["graph_health"] = {"label": "unsupported_language_limited"}

    with patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "intent": "feature",
                "confidence": "medium",
                "files_to_inspect_first": [],
                "files_likely_to_modify": [],
            },
        },
    ):
        result = api.plan_change("add logging")

    assert result.get("ok") is False
    assert result.get("status") == "unsupported_language_limited"
    assert result.get("insufficient_evidence") is True


def test_weak_graph_build_allows_with_exact_file_evidence(tiny_scan):
    root, _ = tiny_scan
    api._STATE["scan"]["graph_health"] = {"label": "unsupported_language_limited"}
    target = "a.py"

    with patch(
        "jarvis_desktop.planning_engine.plan_change",
        return_value={
            "ok": True,
            "plan": {
                "intent": "feature",
                "confidence": "medium",
                "files_to_inspect_first": [target],
                "repository_evidence": {
                    "file_evidences": [
                        {"path": target, "matching_symbols": ["x"], "evidence_score": 80},
                    ],
                },
            },
        },
    ):
        result = api.plan_change("add logging")

    assert result.get("ok") is True


def test_concurrent_select_and_export_no_wrong_repo_memory(tmp_path):
    _fresh_state()
    root_a = _tiny_repo(tmp_path, "repo_a", "a.py", "x = 1\n")
    root_b = _tiny_repo(tmp_path, "repo_b", "b.py", "y = 2\n")
    assert api.scan_repository(str(root_a))["ok"]

    mismatches: list[tuple[str, str]] = []
    barrier = threading.Barrier(2)

    def flip_paths() -> None:
        barrier.wait()
        for _ in range(40):
            api.select_repository(str(root_b))
            api.select_repository(str(root_a))
            api.scan_repository(str(root_a))

    def export_loop() -> None:
        barrier.wait()
        for _ in range(40):
            pkt = api.session_export_packet()
            if not pkt.get("ok"):
                continue
            path = os.path.abspath(str(api._STATE.get("path") or ""))
            scan_path = os.path.abspath(
                str((api._STATE.get("scan") or {}).get("repo_path") or path)
            )
            if path != scan_path:
                mismatches.append((path, scan_path))
            mem = api._STATE.get("_current_memory") or {}
            if mem and os.path.abspath(str(mem.get("repo_path") or "")) != scan_path:
                mismatches.append((path, str(mem.get("repo_path"))))

    t1 = threading.Thread(target=flip_paths)
    t2 = threading.Thread(target=export_loop)
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert not mismatches


def test_support_diagnostics_include_trust_integrity(tiny_scan):
    _, _ = tiny_scan
    diag = api.beta_diagnostics()
    assert "trust_integrity" in diag
    assert diag["trust_integrity"].get("signature_version") == ti.SIGNATURE_VERSION
    assert "memory_persistence_status" in diag["trust_integrity"]

    env = environment_status()
    assert "trust_integrity" in env
    assert env["trust_integrity"].get("state_lock") == "threading.RLock"


def test_signature_v2_uses_index_manifest_not_arbitrary_cap(tmp_path):
    """Edits to alphabetically-late files must invalidate signature (no 2500 cap)."""
    root = tmp_path / "wide"
    root.mkdir()
    (root / "aaa.py").write_text("a = 1\n", encoding="utf-8")
    (root / "zzz.py").write_text("z = 1\n", encoding="utf-8")

    _fresh_state()
    assert api.scan_repository(str(root))["ok"]
    sig_before = api._STATE["scan"]["signature_v2"]["signature"]

    (root / "zzz.py").write_text("z = 999\n", encoding="utf-8")
    live = ti.compute_signature_v2(
        str(root),
        {"mode": "entire_repo"},
        indexed_files=api._STATE["index"]["files"],
        include_content_hash=True,
    )
    assert live["signature"] != sig_before
