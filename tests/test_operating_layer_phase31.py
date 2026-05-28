"""Phase 31 — unified JARVIS status center."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from actions.operating_layer_actions import ShowJarvisStatusAction
from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import ActionStatus, CommandRequest, Intent
from reliability.jarvis_status import (
    build_jarvis_status_report,
    redact_secrets,
)


def test_classify_show_jarvis_status():
    r = classify_rules("show jarvis status")
    assert r.intent == Intent.SHOW_JARVIS_STATUS


def test_registry_has_show_jarvis_status():
    reg = ActionRegistry()
    assert reg.has(Intent.SHOW_JARVIS_STATUS.value)


def test_status_report_all_sections():
    body = build_jarvis_status_report()
    for section in (
        "overall_status",
        "runtime",
        "voice",
        "overlay",
        "task_agent",
        "patch_system",
        "trading",
        "browser_dom",
        "guided_ui",
        "workspaces",
        "startup_health",
        "safety",
    ):
        assert f"## {section}" in body


def test_missing_optional_files_degraded_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr("reliability.jarvis_status.DATA_DIR", tmp_path / "nodata")
    monkeypatch.setattr("reliability.jarvis_status.TRADING_PROJECT_ROOT", tmp_path / "notrade")
    body = build_jarvis_status_report()
    assert "degraded" in body.lower() or "missing" in body.lower()
    assert "## overall_status" in body


def test_secrets_redacted():
    raw = "api_key=supersecret123 token=abc12345 password=hunter2"
    out = redact_secrets(raw)
    assert "supersecret" not in out
    assert "hunter2" not in out
    assert "REDACTED" in out


def test_disabled_systems_show_disabled(monkeypatch):
    monkeypatch.setattr("reliability.jarvis_status.VOICE_ENABLED", False)
    monkeypatch.setattr("reliability.jarvis_status.BROWSER_DOM_ENABLED", False)
    monkeypatch.setattr("reliability.jarvis_status.GUIDED_UI_ENABLED", False)
    body = build_jarvis_status_report()
    assert "voice: disabled" in body
    assert "browser_dom: disabled" in body
    assert "guided_ui: disabled" in body


def test_degraded_subsystem_does_not_crash_whole_report():
    with patch(
        "reliability.jarvis_status._collect_trading",
        side_effect=RuntimeError("simulated failure"),
    ):
        body = build_jarvis_status_report()
    assert "## trading" in body
    assert "status: degraded" in body
    assert "## safety" in body


def test_action_read_only_success():
    r = ShowJarvisStatusAction().execute(CommandRequest(raw_text="show jarvis status"))
    assert r.status == ActionStatus.SUCCESS
    assert "router_security_registry: intact" in r.summary
    assert "api_key=" not in r.summary.lower() or "REDACTED" in r.summary


def test_no_raw_env_secrets_in_report(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    body = build_jarvis_status_report()
    assert "sk-test-secret" not in body
