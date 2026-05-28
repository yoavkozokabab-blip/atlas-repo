"""Phase 33 — approval inbox."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from actions.approval_inbox_actions import (
    ApprovePendingActionAction,
    ClearApprovalsAction,
    RejectPendingActionAction,
    ShowApprovalsAction,
)
from actions.registry import ActionRegistry
from approvals.inbox import (
    build_safe_payload,
    clear_inbox,
    format_approvals_report,
    list_approval_items,
    record_pending_approval,
    redact_text,
    reset_inbox_store,
)
from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from config import CONFIRMATION_REQUIRED_INTENTS
from core.types import ActionStatus, CommandRequest, CommandResult, Intent


@pytest.fixture(autouse=True)
def _inbox_path(tmp_path, monkeypatch):
    path = tmp_path / "approval_inbox.json"
    monkeypatch.setattr("approvals.inbox.APPROVAL_INBOX_PATH", path)
    reset_inbox_store()
    yield
    reset_inbox_store()


def test_redaction_and_no_patch_in_payload():
    req = CommandRequest(
        raw_text="apply patch api_key=bad",
        intent=Intent.APPLY_TASK_PATCH,
        params={"unified_diff": "--- a/x\n+++ b/x\n+line", "password": "x"},
    )
    payload = build_safe_payload(req)
    assert payload["params"]["unified_diff"] == "[omitted]"
    assert "REDACTED" in redact_text(req.raw_text) or "bad" not in redact_text(req.raw_text)


def test_pending_confirmation_creates_inbox_item():
    req = CommandRequest(
        raw_text="apply task patch",
        intent=Intent.APPLY_TASK_PATCH,
        params={"step": "1"},
    )
    item_id = record_pending_approval("cid123", req, summary="needs confirm")
    assert item_id
    items = list_approval_items(status="pending")
    assert len(items) == 1
    assert items[0].confirmation_id == "cid123"
    assert items[0].intent == "apply_task_patch"
    assert "unified_diff" not in json.dumps(items[0].safe_payload)


def test_show_approvals_lists_safe_summaries():
    record_pending_approval(
        "c1",
        CommandRequest(raw_text="focus window Chrome", intent=Intent.FOCUS_WINDOW),
    )
    r = ShowApprovalsAction().execute(
        CommandRequest(raw_text="show approvals", intent=Intent.SHOW_APPROVALS)
    )
    assert r.status == ActionStatus.SUCCESS
    assert "focus_window" in r.summary
    assert "api_key" not in r.summary.lower()


def test_reject_does_not_execute():
    record_pending_approval(
        "rej1",
        CommandRequest(raw_text="shutdown jarvis", intent=Intent.SHUTDOWN_JARVIS),
    )
    registry = MagicMock()
    r = RejectPendingActionAction().execute(
        CommandRequest(raw_text="reject pending action", intent=Intent.REJECT_PENDING_ACTION)
    )
    assert r.status == ActionStatus.SUCCESS
    registry.execute.assert_not_called()
    assert list_approval_items(status="pending") == []


def test_approve_uses_router_process_path():
    record_pending_approval(
        "app1",
        CommandRequest(
            raw_text="show capabilities",
            intent=Intent.SHOW_CAPABILITIES,
            params={},
        ),
    )
    registry = ActionRegistry()
    with patch.object(CommandRouter, "_finalize"):
        with patch.object(
            CommandRouter,
            "_process",
            return_value=CommandResult(
                intent=Intent.SHOW_CAPABILITIES,
                status=ActionStatus.SUCCESS,
                summary="ok",
            ),
        ) as proc:
            r = ApprovePendingActionAction(registry).execute(
                CommandRequest(
                    raw_text="approve pending action",
                    intent=Intent.APPROVE_PENDING_ACTION,
                )
            )
    assert r.status == ActionStatus.SUCCESS
    proc.assert_called_once()
    call_args = proc.call_args[0][0]
    assert call_args.confirmed is True
    assert call_args.intent == Intent.SHOW_CAPABILITIES


def test_router_records_inbox_on_confirmation_required(monkeypatch):
    monkeypatch.setattr(
        "config.CONFIRMATION_REQUIRED_INTENTS",
        frozenset({"apply_task_patch"}),
    )
    router = CommandRouter()
    with patch.object(router.registry, "execute") as execute:
        execute.side_effect = AssertionError("should not execute before confirm")
        result = router.route("apply task patch")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    pending = list_approval_items(status="pending")
    assert len(pending) == 1


def test_clear_keeps_active_pending():
    record_pending_approval("p1", CommandRequest(raw_text="a", intent=Intent.FOCUS_WINDOW))
    record_pending_approval("p2", CommandRequest(raw_text="b", intent=Intent.CLEAR_CLIPBOARD))
    items = list_approval_items()
    items[0].status = "rejected"
    items[1].status = "completed"
    from approvals.inbox import _save_items

    _save_items(items)
    record_pending_approval("p3", CommandRequest(raw_text="c", intent=Intent.MINIMIZE_WINDOW))
    removed, kept = clear_inbox()
    assert removed >= 2
    assert kept >= 1
    assert any(i.status == "pending" for i in list_approval_items())


def test_corrupted_inbox_degrades_safely(tmp_path, monkeypatch):
    path = tmp_path / "approval_inbox.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr("approvals.inbox.APPROVAL_INBOX_PATH", path)
    items = list_approval_items()
    assert items == []
    r = ShowApprovalsAction().execute(
        CommandRequest(raw_text="show approvals", intent=Intent.SHOW_APPROVALS)
    )
    assert r.status == ActionStatus.SUCCESS


def test_inbox_write_failure_non_fatal(monkeypatch):
    monkeypatch.setattr("approvals.inbox._save_items", lambda _items: False)
    assert record_pending_approval("x", CommandRequest(raw_text="t", intent=Intent.UNKNOWN)) is None


def test_classify_phase33_intents():
    assert classify_rules("show approvals").intent == Intent.SHOW_APPROVALS
    assert classify_rules("approve pending action").intent == Intent.APPROVE_PENDING_ACTION
    assert classify_rules("reject pending action").intent == Intent.REJECT_PENDING_ACTION
    assert classify_rules("clear approvals").intent == Intent.CLEAR_APPROVALS


def test_registry_handlers():
    reg = ActionRegistry()
    for intent in (
        Intent.SHOW_APPROVALS,
        Intent.APPROVE_PENDING_ACTION,
        Intent.REJECT_PENDING_ACTION,
        Intent.CLEAR_APPROVALS,
    ):
        assert reg.has(intent.value)
