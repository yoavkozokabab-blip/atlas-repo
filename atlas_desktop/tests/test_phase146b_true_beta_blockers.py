"""Phase 146B — true beta blocker fixes (startup, demo impact, routing, export, feedback)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api, install_support, server

STATIC = Path(__file__).resolve().parents[1] / "static"


@pytest.fixture(autouse=True)
def _demo_loaded(local_guest_account):
    status, payload = server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    assert status == 200, payload
    assert payload["ok"] is True
    yield


def test_startup_ready_without_env_override(monkeypatch, tmp_path):
    # Exercise production fallback behavior against a fake user profile. Test
    # mode deliberately refuses a missing override because it could otherwise
    # resolve to the real user's canonical registry.
    fake_home = tmp_path / "fake-user"
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("ATLAS_TEST_MODE", "0")
    monkeypatch.delenv("ATLAS_DESKTOP_DATA", raising=False)
    monkeypatch.delenv("JARVIS_DESKTOP_DATA", raising=False)
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache

    reset_desktop_data_dir_cache()
    checks = install_support.startup_checks()
    assert checks["ready"] is True
    info = checks.get("data_dir_info") or {}
    assert checks["data_dir"]
    assert info.get("path")


def test_diagnostics_exposes_data_dir():
    _, diag = server.dispatch("GET", "/api/system/diagnostics")
    assert diag["ok"] is True
    assert diag.get("data_dir", {}).get("path")


def test_demo_impact_quick_start_target():
    imp = api.impact("core/hub.py")
    assert imp["ok"] is True
    assert imp.get("mock") is not True


def test_build_rate_limiting_intent():
    res = api.plan_change("add rate limiting")
    assert res["ok"] is True
    assert res["plan"]["intent"] == "rate_limiting"
    assert res["plan"].get("domain_knowledge", {}).get("concept_id") == "rate_limiting"


def test_investigate_duplicate_events_not_trading():
    res = api.investigate_symptom("why are duplicate events being fired")
    assert res["ok"] is True
    plan = res["plan"]
    assert plan["intent"] == "duplicate_events"
    dk = plan.get("domain_knowledge") or {}
    assert dk.get("concept_id") != "ema"
    assert dk.get("domain") != "trading"


def test_export_atlas_branding():
    packet = api.context_export("claude", "compact")
    assert packet["ok"] is True
    text = packet.get("text") or ""
    assert "ATLAS REPOSITORY CONTEXT" in text
    assert "JARVIS REPOSITORY CONTEXT" not in text


def test_feedback_local_wording():
    fb = (STATIC / "feedback.js").read_text(encoding="utf-8")
    assert "Save locally" in fb
    assert "Send feedback" not in fb


def test_phase146b_report_exists():
    report = Path(__file__).resolve().parents[2] / "reports" / "phase146b_true_beta_blocker_fixes.md"
    if not report.is_file():
        pytest.skip("historical phase report not shipped in the product repo")
