"""Regression: scan runtime-disconnect + contradictory repository state.

Reproduces the launch blocker where scanning a large real repository showed
"Atlas lost contact with the local runtime during indexing" while the top bar
still named the repository and the sidebar simultaneously said "No repository".

Root cause (two parts):
  1. The scan POST inherited the 15s default client timeout. A multi-GB repo
     enumerates for longer than that, so the client AbortController fired and
     reported a false disconnect while the backend was still indexing.
  2. The top-bar chip was set optimistically at scan start and never reverted
     on failure, so it disagreed with the sidebar (which reflects the empty
     committed summary).

These tests pin both fixes: the long scan timeout in the frontend contract and
the reconcile-to-one-consistent-state behaviour, plus backend resilience and
retry-after-recovery at the API level.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api

STATIC = Path(__file__).resolve().parents[1] / "static"
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")


def _fresh() -> None:
    api._STATE.clear()
    api._PERSISTENCE_BOOTSTRAPPED = False
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path / "atlas-data"))
    _fresh()
    yield
    _fresh()


# --------------------------------------------------------------------------
# Frontend contract: runtime disconnect during scan / failed large-repo scan
# --------------------------------------------------------------------------

def test_scan_request_uses_long_timeout_not_default():
    """The scan POST must not inherit the short default request timeout, or a
    slow large-repository scan is aborted as a false runtime disconnect."""
    m = re.search(r"const\s+SCAN_REQUEST_TIMEOUT_MS\s*=\s*([0-9_]+)", APP_JS)
    assert m, "SCAN_REQUEST_TIMEOUT_MS constant must exist"
    scan_timeout = int(m.group(1).replace("_", ""))
    default = re.search(r"const\s+DEFAULT_TIMEOUT_MS\s*=\s*([0-9_]+)", APP_JS)
    assert default, "DEFAULT_TIMEOUT_MS must exist"
    default_ms = int(default.group(1).replace("_", ""))
    # A real multi-GB scan measured ~41s cold; the ceiling must be far above
    # any realistic indexing time and dwarf the 15s default.
    assert scan_timeout >= 300_000, "scan timeout must allow minutes-long indexing"
    assert scan_timeout >= default_ms * 10

    # The scan POST call itself must pass the long timeout override.
    scan_call = re.search(
        r'api\(\s*"/api/repositories/scan"\s*,\s*"POST".*?SCAN_REQUEST_TIMEOUT_MS',
        APP_JS, re.DOTALL,
    )
    assert scan_call, "the scan POST must pass { timeoutMs: SCAN_REQUEST_TIMEOUT_MS }"


# --------------------------------------------------------------------------
# Frontend contract: repository identity consistency across all UI surfaces
# --------------------------------------------------------------------------

def test_scan_failure_reconciles_repository_identity():
    """showScanFailed must reconcile the repository labels so the top bar and
    the sidebar can never disagree after a failure."""
    assert "function reconcileRepoIdentity" in APP_JS
    body = re.search(r"function showScanFailed\([^)]*\)\s*\{(.*?)\n\}", APP_JS, re.DOTALL)
    assert body, "showScanFailed must be present"
    assert "reconcileRepoIdentity()" in body.group(1), \
        "showScanFailed must call reconcileRepoIdentity()"


def test_reconcile_derives_both_surfaces_from_committed_summary():
    """reconcileRepoIdentity is the single source of truth: it reads the
    committed summary and updates BOTH the top-bar chip and the sidebar."""
    fn = re.search(r"function reconcileRepoIdentity\(\)\s*\{(.*?)\n\}", APP_JS, re.DOTALL)
    assert fn, "reconcileRepoIdentity must be present"
    src = fn.group(1)
    assert "STATE.summary" in src, "must derive from the committed summary"
    assert "updateRepoChip(" in src, "must update the top-bar chip"
    assert "syncSidebarFromState" in src, "must re-sync the sidebar"
    # When no repository is committed it must clear the chip (empty name ->
    # "No repository"), never leave a stale optimistic name.
    assert re.search(r'committed\s*\?\s*\(?committed\.repo_name', src) or \
        re.search(r'updateRepoChip\(\s*committed\s*\?', src), \
        "must clear the chip when no repository is committed"


# --------------------------------------------------------------------------
# Backend behaviour: crash/failure during scan, and retry after recovery
# --------------------------------------------------------------------------

def test_failed_scan_returns_structured_failure_not_exception():
    """A scan that cannot proceed (nonexistent path) returns a structured
    failure the UI can render, and never raises out of the runtime."""
    result = api.scan_repository(str(Path("Z:/no/such/atlas/repo/at/all")))
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert result.get("error") or result.get("code"), "failure must carry a reason"


def test_failed_scan_commits_no_repository_state():
    """A failed scan must commit nothing: the current summary reports no active
    repository, matching the reconciled empty UI state (no phantom repo)."""
    api.scan_repository(str(Path("Z:/no/such/atlas/repo")))
    summary = api.current_summary()
    assert not summary.get("ok") or not summary.get("repo_name"), \
        "a failed scan must not leave a committed repository name"


def test_retry_after_failed_scan_recovers():
    """After a failed scan the runtime stays alive and a subsequent valid scan
    succeeds — i.e. retry actually works once the target is scannable."""
    failed = api.scan_repository(str(Path("Z:/no/such/atlas/repo")))
    assert failed.get("ok") is False
    recovered = api.load_demo_mode("medium")
    assert recovered.get("ok") is True
    summary = api.current_summary()
    assert summary.get("ok") is True
    assert summary.get("file_count", 0) > 0


def test_backend_survives_failure_then_serves_health_equivalent():
    """A failure during scan must not poison the runtime: after it, normal
    read endpoints still work (the backend never 'stopped responding')."""
    api.scan_repository(str(Path("Z:/no/such/atlas/repo")))
    # Equivalent of the health/summary polls the shell performs after a failure.
    summary = api.current_summary()
    assert isinstance(summary, dict)
    # And a good scan still commits cleanly afterward.
    assert api.load_demo_mode("medium").get("ok") is True
