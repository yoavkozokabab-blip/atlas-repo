"""v1.0.5 indexing blocker — a scan must never freeze at a mid-stage percent.

Reproduces the reported "stuck ~68% + runtime unavailable" class of failure:
a scan that fails partway must move to a terminal error state so the indexing
modal releases, progress never sticks at 68/52/42, and 100% is reached only
on committed completion.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api
import atlas_desktop.api as A


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


def _repo(tmp_path: Path, name: str, n: int = 40) -> str:
    r = tmp_path / name
    r.mkdir()
    for i in range(n):
        (r / f"m{i}.py").write_text(f"import m{max(0, i - 1)}\ndef f{i}(): return {i}\n", encoding="utf-8")
    return str(r)


def test_normal_scan_reaches_completed_100(data_dir, tmp_path):
    _fresh()
    assert api.scan_repository(_repo(tmp_path, "ok"))["ok"]
    st = api.scan_status()
    assert st["stage"] == "completed"
    assert st["progress_pct"] == 100
    assert st["is_terminal"] is True
    assert st["scan_failed"] is False


def test_scan_stage_map_has_terminal_error_states():
    for stage in ("error", "interrupted", "cancelled"):
        assert stage in api._SCAN_STAGE_PROGRESS
        assert stage in api._SCAN_TERMINAL_STAGES
        assert api._SCAN_STAGE_PROGRESS[stage][0] == 0  # never a mid-stage percent


def test_propagating_failure_moves_to_terminal_error(data_dir, tmp_path, monkeypatch):
    _fresh()
    # Force a failure that propagates out of the scan (not the internally
    # caught risk stage), on a fresh repo so no cache short-circuits it.
    monkeypatch.setattr(A, "_light_index", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("runtime loss")))
    result = api.scan_repository(_repo(tmp_path, "boom"))
    assert result["ok"] is False
    st = api.scan_status()
    # Must NOT be frozen at a mid-scan percent (68 = ranking_risks, etc.).
    assert st["stage"] == "error"
    assert st["progress_pct"] == 0
    assert st["is_terminal"] is True
    assert st["scan_failed"] is True
    assert st["scan_error"]


def test_recovery_after_failure(data_dir, tmp_path, monkeypatch):
    _fresh()
    monkeypatch.setattr(A, "_light_index", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    api.scan_repository(_repo(tmp_path, "bad"))
    monkeypatch.undo()
    assert api.scan_repository(_repo(tmp_path, "good"))["ok"]
    st = api.scan_status()
    assert st["stage"] == "completed" and st["progress_pct"] == 100


def test_cancel_is_prompt_and_terminalizes(data_dir):
    _fresh()
    api._STATE["scan_job"] = {"id": "s", "cancelled": False, "stage": "building_graph"}
    import time
    t0 = time.time()
    out = api.cancel_scan()
    assert (time.time() - t0) < 1.0
    assert out["cancelled"] is True
    assert out["job"]["stage"] == "cancel_requested"


def test_stale_scan_does_not_survive_restart(data_dir, tmp_path):
    _fresh()
    api.scan_repository(_repo(tmp_path, "r"))
    # Simulate a crash mid-scan: leave a stuck stage, then "restart".
    api._STATE["scan_job"]["stage"] = "ranking_risks"
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api._STATE.update({"scan_job": {"id": None, "cancelled": False, "stage": "idle"}})
    st = api.scan_status()
    assert st["stage"] == "idle"
    assert st["is_terminal"] is True
