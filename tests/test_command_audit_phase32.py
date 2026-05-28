"""Phase 32 — command audit trail."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from actions.diagnostics_actions import ShowCommandAuditAction
from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from diagnostics.command_audit import (
    append_audit_event,
    build_audit_entry,
    format_audit_report,
    read_last_audit_entries,
    redact_text,
    reset_audit_store,
)


@pytest.fixture(autouse=True)
def _audit_path(tmp_path, monkeypatch):
    path = tmp_path / "command_audit.jsonl"
    monkeypatch.setattr("diagnostics.command_audit.COMMAND_AUDIT_PATH", path)
    reset_audit_store()
    yield
    reset_audit_store()


def test_redact_secrets():
    raw = "api_key=secret123 password=hunter2 token=abc"
    out = redact_text(raw)
    assert "secret123" not in out
    assert "hunter2" not in out
    assert "REDACTED" in out


def test_build_audit_omits_patch_body():
    req = CommandRequest(
        raw_text="propose patch",
        intent=Intent.PROPOSE_TASK_PATCH,
        params={"unified_diff": "--- a/foo\n+++ b/foo\n+line"},
    )
    res = CommandResult(
        intent=Intent.PROPOSE_TASK_PATCH,
        status=ActionStatus.SUCCESS,
        summary="Unified diff (preview only):\n```diff\n+secret line\n```",
    )
    entry = build_audit_entry(req, res, 12)
    assert entry["params"].get("unified_diff") == "[omitted]"
    assert "+++ b/" not in entry["summary"]
    assert "omitted" in entry["summary"].lower() or "REDACTED" in entry["summary"]


def test_append_writes_jsonl():
    req = CommandRequest(raw_text="show capabilities", intent=Intent.SHOW_CAPABILITIES)
    res = CommandResult(
        intent=Intent.SHOW_CAPABILITIES,
        status=ActionStatus.SUCCESS,
        summary="Capabilities listed.",
    )
    assert append_audit_event(req, res, 5) is True
    entries = read_last_audit_entries(5)
    assert len(entries) == 1
    assert entries[0]["intent"] == "show_capabilities"


def test_show_last_entries_default_20():
    req = CommandRequest(raw_text="x", intent=Intent.SHOW_SYSTEM_STATUS)
    res = CommandResult(
        intent=Intent.SHOW_SYSTEM_STATUS,
        status=ActionStatus.SUCCESS,
        summary="ok",
    )
    for i in range(25):
        append_audit_event(req, res, i)
    entries = read_last_audit_entries(20)
    assert len(entries) == 20
    report = format_audit_report(entries, limit=20)
    assert "audit trail" in report.lower()


def test_show_command_audit_action():
    req = CommandRequest(raw_text="show capabilities", intent=Intent.SHOW_CAPABILITIES)
    res = CommandResult(
        intent=Intent.SHOW_CAPABILITIES,
        status=ActionStatus.SUCCESS,
        summary="done",
    )
    append_audit_event(req, res, 1)
    r = ShowCommandAuditAction().execute(
        CommandRequest(raw_text="show command audit", intent=Intent.SHOW_COMMAND_AUDIT)
    )
    assert r.status == ActionStatus.SUCCESS
    assert "show_capabilities" in r.summary


def test_classify_show_command_audit():
    r = classify_rules("show command audit")
    assert r.intent == Intent.SHOW_COMMAND_AUDIT


def test_registry_has_handler():
    assert ActionRegistry().has(Intent.SHOW_COMMAND_AUDIT.value)


def test_audit_failure_non_fatal_router(monkeypatch):
    monkeypatch.setattr(
        "diagnostics.command_audit.append_audit_event",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit down")),
    )

    class OkAction:
        intent = Intent.SHOW_CAPABILITIES.value

        def execute(self, request):
            return CommandResult(
                intent=Intent.SHOW_CAPABILITIES,
                status=ActionStatus.SUCCESS,
                summary="ok",
            )

    router = CommandRouter(registry=ActionRegistry())
    router.registry._actions[Intent.SHOW_CAPABILITIES.value] = OkAction()

    with patch.object(router, "_log_command"):
        result = router.route("show capabilities")
    assert result.status == ActionStatus.SUCCESS


def test_append_failure_returns_false():
    req = CommandRequest(raw_text="x", intent=Intent.UNKNOWN)
    res = CommandResult(intent=Intent.UNKNOWN, status=ActionStatus.FAILED, summary="fail")
    with patch("pathlib.Path.open", side_effect=OSError("denied")):
        assert append_audit_event(req, res, 1) is False
