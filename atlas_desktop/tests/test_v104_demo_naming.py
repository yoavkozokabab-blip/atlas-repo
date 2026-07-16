"""Regression tests for v1.0.4 demo repository naming stability.

Guards the corrected behavior:
  * The visible demo title is "Atlas Demo — Medium" (no redundant "demo").
  * canonical_name stays "medium_repo".
  * The human-facing title survives a simulated restart instead of flipping
    back to the raw folder basename.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api
from atlas_desktop import repository_memory as rm


DISPLAY = "Atlas Demo — Medium"
CANONICAL = "medium_repo"


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


def _medium_available() -> bool:
    return os.path.isdir(api.demo_repo_path("medium"))


def test_demo_load_uses_clean_display_name(data_dir):
    if not _medium_available():
        pytest.skip("bundled medium demo not present in this tree")
    _fresh()
    result = api.load_demo_mode("medium")
    assert result.get("ok"), result
    # No redundant "demo" in the visible title.
    assert result["repo_name"] == DISPLAY
    assert result["display_name"] == DISPLAY
    assert "Medium demo" not in result["repo_name"]
    # Canonical is the folder basename, exposed distinctly.
    assert result["canonical_name"] == CANONICAL


def test_summary_reports_display_and_canonical(data_dir):
    if not _medium_available():
        pytest.skip("bundled medium demo not present in this tree")
    _fresh()
    api.load_demo_mode("medium")
    summary = api.current_summary()
    assert summary["repo_name"] == DISPLAY
    assert summary["display_name"] == DISPLAY
    assert summary["canonical_name"] == CANONICAL


def test_demo_title_survives_restart(data_dir):
    if not _medium_available():
        pytest.skip("bundled medium demo not present in this tree")
    _fresh()
    api.load_demo_mode("medium")
    repo_path = api._STATE["scan"]["repo_path"]
    rid = rm.repo_id(repo_path)

    # Simulate a full restart: drop live state, re-bootstrap from disk.
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    status = api.bootstrap_persistence(auto_restore=True)
    assert status.get("restored") is True
    assert rm.repo_id(str(api._STATE.get("path"))) == rid

    restored_summary = api.current_summary()
    # The pretty title must NOT flip back to the raw folder basename.
    assert restored_summary["repo_name"] == DISPLAY, restored_summary["repo_name"]
    assert restored_summary["repo_name"] != CANONICAL
    assert "Medium demo" not in restored_summary["repo_name"]
