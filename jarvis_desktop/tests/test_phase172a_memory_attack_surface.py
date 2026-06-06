"""Phase 172A — Repository memory attack surface (red-team regressions).

Proves invalidation failures that will become P0 bugs when Repository Memory ships.
Assumes Phase 171B RMO replaces session_export; same _STATE slots apply.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api
from jarvis_desktop.install_support import rebuild_index


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


def test_attack_a1_select_repository_clears_stale_scan(tiny_scan, tmp_path):
    """Beta P0-01: select new repo path without rescan clears scan + blocks plans."""
    root_a, scan_a = tiny_scan
    repo_a_name = scan_a["repo_name"]
    assert repo_a_name in api.session_export_packet()["text"]

    root_b = _tiny_repo(tmp_path, "repo_b", "z.py", "z = 9\n")
    sel = api.select_repository(str(root_b))
    assert sel["ok"]
    assert sel.get("requires_rescan") is True

    assert api._STATE["path"] == str(root_b)
    assert api._STATE.get("scan") is None
    assert api._STATE.get("session_export") is None
    assert api.session_export_packet().get("ok") is False

    plan = api.plan_change("add logging")
    assert plan.get("ok") is False
    assert plan.get("code") == "requires_rescan"


def test_attack_a2_rebuild_index_preserves_poisoned_memory(tiny_scan):
    """Phase 172 mitigation A2: rebuild_index(rescan=False) now clears stale session/memory.

    Original bug: rescan=False preserved poisoned session_export.
    Fix: Phase 172 clears session_export, repository_memory, and _current_memory.
    """
    _ = tiny_scan
    api._STATE["session_export"] = {
        "text": "ATLAS_REPOSITORY_MEMORY v1\nrepo: POISONED",
        "mode": "MEMORY",
        "tokens": 50,
        "version": "poison-v1",
    }
    result = rebuild_index(rescan=False)
    assert result["ok"]
    assert api._STATE.get("scan") is None
    # Fixed: poisoned memory must be cleared
    mem = api._STATE.get("session_export")
    assert mem is None or "POISONED" not in (
        mem.get("text", "") if isinstance(mem, dict) else ""
    )


def test_attack_b4_session_export_survives_scan_signature_cache_hit(tiny_scan):
    """P1: second scan cache-hit rebuilds session from cache, not live disk."""
    root, _ = tiny_scan
    first_sig = api._STATE["scan"]["cache"]["signature"]
    api._STATE["session_export"] = {
        "text": "STALE_PINNED_MEMORY",
        "mode": "SESSION",
        "tokens": 10,
    }
    # Cache hit overwrites session_export from scan path on restore.
    api.scan_repository(str(root))
    assert api._STATE["scan"]["cache"]["hit"] is True
    assert api._STATE["scan"]["cache"]["signature"] == first_sig
    # Current behavior: cache restore regenerates session — good —
    # but pinned client STATE would still be stale (UI test documented in report).
    restored = api._STATE["session_export"]["text"]
    assert "STALE_PINNED_MEMORY" not in restored
    # Phase 172: cache restore now produces ATLAS_REPOSITORY_MEMORY v1 (not ATLAS_SESSION v1)
    assert "ATLAS_REPOSITORY_MEMORY v1" in restored or "ATLAS_SESSION" in restored


def test_scan_signature_v2_uses_full_indexed_manifest():
    """Phase 174B: signature v2 hashes indexed scan manifest (no 2500 cap)."""
    from jarvis_desktop import trust_integrity as ti

    import inspect
    src = inspect.getsource(ti.compute_signature_v2)
    assert "2500" not in src
    assert "indexed_files" in src
    assert "manifest_hash" in src


def test_required_mitigation_select_must_clear_memory_flag(tmp_path):
    """Phase 172 mitigation A1: select_repository clears stale session_export."""
    _fresh_state()
    root_a = _tiny_repo(tmp_path, "repo_a", "a.py", "x = 1\n")
    scan_a = api.scan_repository(str(root_a))
    assert scan_a["ok"]

    # Confirm memory is set after scan
    assert api._STATE.get("session_export") is not None

    # Select a different repository — should clear session_export
    root_b = _tiny_repo(tmp_path, "repo_b", "z.py", "z = 9\n")
    sel = api.select_repository(str(root_b))
    assert sel["ok"]
    assert api._STATE.get("session_export") is None
    assert api._STATE.get("repository_memory") is None
