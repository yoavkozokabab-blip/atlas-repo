"""v1.0.5 analytics opt-out — authoritative, persistent, queue-clearing.

Disabling analytics must block every subsequent desktop event (local log and
remote queue), clear queued events, survive restart, and never affect product
behavior. The Settings UI must reflect the backend preference.
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    # Reload emitter modules so their cached data dirs pick up the tmp root.
    import atlas_desktop.analytics as analytics
    import atlas_desktop.analytics_remote as remote
    importlib.reload(remote)
    importlib.reload(analytics)
    return analytics, remote


def _events(analytics) -> int:
    p = analytics.analytics_file_path()
    if not os.path.isfile(p):
        return 0
    return sum(1 for _ in open(p, encoding="utf-8"))


def test_enabled_event_is_written(data_dir):
    analytics, remote = data_dir
    assert remote.analytics_enabled() is True  # opt-out model: default on
    r = analytics.track_event("impact_completed", duration_ms=10)
    assert r["ok"] is True and "skipped" not in r
    assert _events(analytics) == 1


def test_disabled_blocks_local_and_remote(data_dir):
    analytics, remote = data_dir
    remote.set_analytics_opt_out(True)
    assert remote.analytics_enabled() is False
    before = _events(analytics)
    r = analytics.track_event("impact_completed", duration_ms=10)
    assert r.get("skipped") == "analytics_disabled"
    assert _events(analytics) == before  # nothing written locally
    # Remote path also refuses to enqueue.
    remote.track_pipeline_event("impact_completed", installation_id="install-abcdef12",
                                app_version="1.0.5", build_commit="deadbeef", properties={})
    assert remote._load_queue() == []


def test_disable_clears_existing_queue(data_dir):
    analytics, remote = data_dir
    remote.track_pipeline_event("impact_completed", installation_id="install-abcdef12",
                                app_version="1.0.5", build_commit="deadbeef", properties={})
    assert len(remote._load_queue()) >= 1
    remote.set_analytics_opt_out(True)
    assert remote._load_queue() == []  # queued-but-unsent events dropped


def test_disabled_state_survives_restart(data_dir):
    analytics, remote = data_dir
    remote.set_analytics_opt_out(True)
    # "Restart": reload the modules; the on-disk preference must persist.
    importlib.reload(remote)
    importlib.reload(analytics)
    assert remote.analytics_enabled() is False
    r = analytics.track_event("app_screen_viewed", screen="home")
    assert r.get("skipped") == "analytics_disabled"


def test_direct_emitter_blocked_while_disabled(data_dir):
    analytics, remote = data_dir
    remote.set_analytics_opt_out(True)
    # A direct low-level emitter call must also be blocked.
    r = analytics.track_event("app_started")
    assert r.get("skipped") == "analytics_disabled"


def test_reenable_restores_emission(data_dir):
    analytics, remote = data_dir
    remote.set_analytics_opt_out(True)
    remote.set_analytics_opt_out(False)
    assert remote.analytics_enabled() is True
    r = analytics.track_event("impact_completed", duration_ms=5)
    assert r["ok"] is True and "skipped" not in r
    assert _events(analytics) == 1


def test_analytics_failure_is_non_blocking_when_enabled(data_dir, monkeypatch):
    analytics, remote = data_dir
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r = analytics.track_event("impact_completed", duration_ms=1)
    assert r["ok"] is False and r["analytics_status"] == "degraded"


def test_preference_carries_no_repository_data(data_dir):
    analytics, remote = data_dir
    remote.set_analytics_opt_out(True)
    import json
    blob = json.dumps(remote._read_json(remote._preferences_path(), {}))
    for forbidden in ("repo", "path", "file", "C:\\", "/home/", "prompt", "answer"):
        assert forbidden.lower() not in blob.lower()


def test_ui_wires_toggle_to_backend_preference():
    static = os.path.join(os.path.dirname(__file__), "..", "static")
    index = open(os.path.join(static, "index.html"), encoding="utf-8").read()
    app = open(os.path.join(static, "app.js"), encoding="utf-8").read()
    shell = open(os.path.join(static, "desktop-shell.js"), encoding="utf-8").read()
    assert 'id="analyticsOptToggle"' in index
    assert "Share pseudonymous usage analytics" in index
    assert 'role="switch"' in index
    assert "setAnalyticsPreference" in app
    assert '/api/analytics/preferences' in app and '/api/analytics/preferences' in shell
