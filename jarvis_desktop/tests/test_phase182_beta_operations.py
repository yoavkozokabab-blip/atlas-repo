"""Phase 182 — beta operations foundation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import analytics, api, operations, server


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from jarvis_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    analytics.reset_analytics_for_tests()
    return str(d)


def _fresh_state() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


def test_installation_identity_stable(data_dir):
    a = operations.get_installation_identity()
    b = operations.get_installation_identity()
    assert a["installation_id"]
    assert a["installation_id"] == b["installation_id"]
    assert Path(data_dir, "operations", "installation.json").is_file()


def test_analytics_pipeline_enriches_events(data_dir):
    operations.pipeline_track_event("test_event", foo="bar")
    rows = analytics._read_events()
    assert rows
    last = rows[-1]
    assert last["event"] == "test_event"
    assert last["installation_id"]
    assert last["pipeline_version"] == operations.PIPELINE_VERSION
    assert last["foo"] == "bar"


def test_beta_insights_requires_admin(data_dir):
    _, res = server.dispatch("GET", "/api/operations/insights")
    assert res["ok"] is False
    assert res["code"] == "admin_disabled"


def test_beta_insights_dashboard_with_admin(data_dir, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    operations.pipeline_track_event("scan_completed", cache_hit=False)
    _, res = server.dispatch("GET", "/api/operations/insights")
    assert res["ok"] is True
    assert res["installation"]["installation_id"]
    assert res["analytics"]["total_events"] >= 1
    assert "token_savings" in res
    assert "update" in res


def test_feedback_inbox_lists_submissions(data_dir, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    _, fb = server.dispatch("POST", "/api/feedback", {
        "category": "bug",
        "message": "Button confusing on export",
        "page": "index.html",
    })
    assert fb["ok"] is True
    _, inbox = server.dispatch("GET", "/api/operations/feedback")
    assert inbox["ok"] is True
    assert len(inbox["items"]) >= 1
    # P1 minimization: items now use "summary" key (truncated, no email/paths).
    assert "Button confusing on export" in inbox["items"][0]["summary"]
    assert inbox["items"][0].get("feedback_id")


def test_token_savings_dashboard_aggregates_exports(data_dir):
    operations.pipeline_track_event(
        "export_created",
        tokens=120,
        full_export_tokens=400,
        minimal_export_tokens=120,
        delta_export_tokens=80,
    )
    dash = operations.token_savings_dashboard()
    assert dash["ok"] is True
    assert dash["from_events"]["export_events"] == 1
    assert dash["from_events"]["active_export_tokens"] == 120
    _, api_res = server.dispatch("GET", "/api/operations/token-savings")
    assert api_res["ok"] is True


def test_crash_registry_records_and_lists(data_dir, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    rec = operations.record_crash("test_crash", "something broke", exc_type="ValueError")
    assert rec["ok"] is True
    _, listed = server.dispatch("GET", "/api/operations/crashes")
    assert listed["ok"] is True
    assert listed["summary"]["total"] >= 1
    assert listed["items"][0]["kind"] == "test_crash"


def test_update_hardening_rejects_malformed_version(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    class _Resp:
        def read(self):
            return json.dumps({"version": "not-a-version"}).encode("utf-8")

        status = 200

        def close(self):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = operations.check_update_hardened()
    assert data["trust_level"] == "malformed"
    assert data["update_available"] is False


def test_update_hardened_allows_valid_newer_version(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    # Derive a strictly-newer minor bump from the current product version so
    # the fixture stays valid as the product version moves.
    from jarvis_desktop.product_info import PRODUCT_VERSION
    _cur = PRODUCT_VERSION.split("-")[0].split(".")
    _newer = f"{_cur[0]}.{int(_cur[1]) + 1}.0"

    class _Resp:
        def read(self):
            return json.dumps({"version": _newer}).encode("utf-8")

        status = 200

        def close(self):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = operations.check_update_hardened()
    assert data["trust_level"] == "trusted"
    assert data["update_available"] is True


def test_health_includes_installation_id(data_dir):
    _, health = server.dispatch("GET", "/api/health")
    assert health.get("installation_id")


def test_scan_failure_records_crash(data_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    _fresh_state()
    missing = str(tmp_path / "does-not-exist-repo")
    api.scan_repository(missing)
    summary = operations.crash_summary()
    assert summary["total"] >= 1


def test_system_identity_endpoint(data_dir):
    _, res = server.dispatch("GET", "/api/system/identity")
    assert res["ok"] is True
    assert res["installation_id"]
    assert res["atlas_version"]
    assert "build_commit" in res
    assert "first_launch" in res
    assert "last_launch" in res


def test_system_identity_stable_across_calls(data_dir):
    _, r1 = server.dispatch("GET", "/api/system/identity")
    _, r2 = server.dispatch("GET", "/api/system/identity")
    assert r1["installation_id"] == r2["installation_id"]
    assert r1["first_launch"] == r2["first_launch"]


def test_update_hardening_rejects_older_version(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    class _Resp:
        def read(self):
            return json.dumps({"version": "0.0.1-beta"}).encode("utf-8")
        status = 200
        def close(self): pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = operations.check_update_hardened()
    assert data["update_available"] is False
    assert data["trust_level"] == "malformed"


def test_update_hardening_same_version(monkeypatch):
    from jarvis_desktop.product_info import PRODUCT_VERSION
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    class _Resp:
        def read(self):
            return json.dumps({"version": PRODUCT_VERSION}).encode("utf-8")
        status = 200
        def close(self): pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    data = operations.check_update_hardened()
    assert data["update_available"] is False
    assert data["trust_level"] == "trusted"


def test_update_hardening_missing_latest_json(monkeypatch):
    import urllib.error
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("not found")),
    )
    data = operations.check_update_hardened()
    assert data["update_available"] is False
    assert data["trust_level"] == "unavailable"


def test_update_hardening_invalid_json(monkeypatch):
    monkeypatch.setenv("ATLAS_UPDATE_CHECK_URL", "https://updates.example/version.json")

    class _BadResp:
        def read(self): return b"not-json"
        status = 200
        def close(self): pass

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _BadResp())
    data = operations.check_update_hardened()
    assert data["update_available"] is False


def test_feedback_survives_multiple_submissions(data_dir, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    for i in range(3):
        server.dispatch("POST", "/api/feedback", {
            "category": "general",
            "message": f"Feedback item {i}",
        })
    _, inbox = server.dispatch("GET", "/api/operations/feedback")
    assert inbox["ok"] is True
    assert len(inbox["items"]) >= 3


def test_crash_registry_capped_at_100(data_dir, monkeypatch):
    monkeypatch.setenv("ATLAS_ADMIN", "1")
    for i in range(5):
        operations.record_crash("test_kind", f"crash {i}")
    _, res = server.dispatch("GET", "/api/operations/crashes")
    assert res["ok"] is True
    assert len(res["items"]) <= 100


def test_token_savings_no_fake_values(data_dir):
    dash = operations.token_savings_dashboard()
    assert dash["ok"] is True
    totals = dash["from_events"]
    assert totals["export_events"] == 0
    assert totals["active_export_tokens"] == 0
