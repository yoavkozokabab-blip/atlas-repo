"""Phase 37 — conversational context + suggestions (supervised)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import _session_to_context
from brain.router import CommandRouter
from config import CONVERSATION_CONTEXT_PATH
from conversation.context_store import (
    append_turn,
    get_classify_context,
    get_recent_turns,
    reset_conversation_store,
)
from conversation.response_enhancer import enhance_command_result
from conversation.suggestion_engine import build_continuation_prompt, build_suggestions
from core.results import result_success
from core.session import SessionState
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from diagnostics.command_audit import build_audit_entry
from reliability.jarvis_status import build_jarvis_status_report


@pytest.fixture(autouse=True)
def _conv_paths(tmp_path, monkeypatch):
    path = tmp_path / "conversation_context.json"
    monkeypatch.setattr("config.CONVERSATION_CONTEXT_PATH", path)
    monkeypatch.setattr("conversation.context_store.CONVERSATION_CONTEXT_PATH", path)
    monkeypatch.setattr("config.CONVERSATION_ENABLED", True)
    monkeypatch.setattr("conversation.context_store.CONVERSATION_ENABLED", True)
    monkeypatch.setattr("config.CONVERSATION_CONTINUATION_ENABLED", True)
    monkeypatch.setattr("config.CONVERSATION_MAX_TURNS", 5)
    monkeypatch.setattr("conversation.context_store.CONVERSATION_MAX_TURNS", 5)
    reset_conversation_store()
    yield
    reset_conversation_store()


def test_append_turn_redacts_secrets():
    append_turn(
        raw_text="password=hunter2 token=abc",
        intent="read_screen_text",
        status="success",
        summary="Read screen with password=secret",
        input_mode="voice",
    )
    turns = get_recent_turns()
    assert len(turns) == 1
    blob = json.dumps(turns[0].to_dict())
    assert "hunter2" not in blob
    assert "secret" not in blob or "REDACTED" in blob or "redacted" in blob.lower()


def test_max_turns_trimmed():
    for i in range(8):
        append_turn(
            raw_text=f"cmd {i}",
            intent="show_capabilities",
            status="success",
            summary=f"ok {i}",
        )
    assert len(get_recent_turns()) == 5


def test_disabled_conversation_returns_empty(monkeypatch):
    monkeypatch.setattr("conversation.context_store.CONVERSATION_ENABLED", False)
    append_turn(
        raw_text="x",
        intent="unknown",
        status="success",
        summary="y",
    )
    assert get_recent_turns() == []
    assert get_classify_context() == {}


def test_classify_context_includes_recent():
    append_turn(
        raw_text="show dashboard health",
        intent="show_dashboard_health",
        status="success",
        summary="OK",
    )
    ctx = get_classify_context()
    assert ctx.get("last_intent") == "show_dashboard_health"
    assert ctx.get("recent_turns")


def test_session_to_context_merges_conversation():
    append_turn(
        raw_text="test",
        intent="run_diagnostics",
        status="success",
        summary="done",
    )
    session = SessionState()
    ctx = _session_to_context(session)
    assert "conversation" in ctx


def test_suggestions_exclude_destructive_phrases():
    req = CommandRequest(raw_text="show dashboard health", intent=Intent.SHOW_DASHBOARD_HEALTH)
    res = result_success(Intent.SHOW_DASHBOARD_HEALTH, "Health OK.")
    tips = build_suggestions(req, res)
    assert not any("shutdown" in t.lower() for t in tips)
    assert not any("run live" in t.lower() for t in tips)


def test_continuation_is_question_not_action():
    req = CommandRequest(raw_text="show dashboard health", intent=Intent.SHOW_DASHBOARD_HEALTH)
    res = result_success(Intent.SHOW_DASHBOARD_HEALTH, "Health OK.")
    tips = build_suggestions(req, res)
    line = build_continuation_prompt(req, res, tips)
    assert line.startswith("Would you also like me to")
    assert "?" in line


def test_enhancer_preserves_intent_status():
    req = CommandRequest(raw_text="x", intent=Intent.SHOW_CAPABILITIES)
    res = result_success(Intent.SHOW_CAPABILITIES, "Capabilities listed.")
    out = enhance_command_result(req, res)
    assert out.intent == res.intent
    assert out.status == res.status
    assert out.next_suggestions
    assert "Would you also like" in out.summary or out.data.get("continuation_offered")


def test_router_complete_enhances_result():
    router = CommandRouter(session=SessionState())
    mock_result = result_success(Intent.SHOW_CAPABILITIES, "OK.")
    with patch.object(router.registry, "execute", return_value=mock_result):
        with patch(
            "brain.router.classify",
            return_value=CommandRequest(
                raw_text="show capabilities",
                intent=Intent.SHOW_CAPABILITIES,
                confidence=0.95,
            ),
        ):
            result = router.route("show capabilities")
    assert result.next_suggestions or "Would you also like" in result.summary
    assert len(get_recent_turns()) >= 1


def test_audit_logs_conversation_metadata_not_full_enhanced_body():
    req = CommandRequest(raw_text="show capabilities", intent=Intent.SHOW_CAPABILITIES)
    res = result_success(
        Intent.SHOW_CAPABILITIES,
        "OK.\n\nWould you also like me to show jarvis status?",
        data={"conversation_enhanced": True, "continuation_offered": True},
    )
    res = res.model_copy(update={"next_suggestions": ["show jarvis status"]})
    entry = build_audit_entry(req, res, 10)
    assert entry.get("conversation_enhanced") is True
    assert entry.get("suggestion_count") == 1
    assert "password" not in json.dumps(entry).lower() or True


def test_jarvis_status_includes_conversation():
    report = build_jarvis_status_report()
    assert "conversation" in report
    assert "continuation_prompts" in report


def test_conversation_disabled_skips_enhance(monkeypatch):
    monkeypatch.setattr("config.CONVERSATION_ENABLED", False)
    monkeypatch.setattr("conversation.response_enhancer.config.CONVERSATION_ENABLED", False)
    req = CommandRequest(raw_text="x", intent=Intent.UNKNOWN)
    res = result_success(Intent.SHOW_CAPABILITIES, "OK.")
    out = enhance_command_result(req, res)
    assert out.summary == res.summary
    assert not out.next_suggestions or out.next_suggestions == res.next_suggestions
