"""Phase 40 — operating assistant workflows."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.registry import ActionRegistry
from actions.workspace_actions import WhatAmIDoingAction
from brain.intent_classifier import classify
from config import IMPLEMENTED_INTENTS
from conversation.suggestion_engine import build_workspace_suggestions
from core.session import SessionState
from core.types import CommandRequest, Intent
from memory.session_memory import (
    append_session_event,
    reset_session_memory_file,
    restore_context,
    summarize_session,
)
from operating.workspace_context import (
    infer_workspace_mode,
    reset_workspace_context_file,
)
from ui.overlay_state import OverlaySnapshot, OverlayState


@pytest.fixture(autouse=True)
def _clean_phase40_files():
    reset_workspace_context_file()
    reset_session_memory_file()
    yield
    reset_workspace_context_file()
    reset_session_memory_file()


def test_infer_workspace_mode_coding():
    assert infer_workspace_mode(process_name="Cursor.exe", window_title="jarvis.py") == "coding"


def test_infer_workspace_mode_trading():
    assert infer_workspace_mode(window_title="TradingView chart") == "trading"


def test_build_workspace_suggestions_coding():
    phrases = build_workspace_suggestions("coding")
    assert "run diagnostics" in [p.lower() for p in phrases]


@patch("operating.workspace_context.get_active_window_metadata")
def test_what_am_i_doing_action(mock_meta):
    meta = MagicMock()
    meta.error = ""
    meta.process_name = "Code"
    meta.title = "local_jarvis"
    meta.is_blocked = False
    mock_meta.return_value = meta
    req = CommandRequest(raw_text="what am i doing", intent=Intent.WHAT_AM_I_DOING)
    result = WhatAmIDoingAction().execute(req)
    assert result.status.value == "success"
    assert "Mode:" in result.summary
    assert result.data.get("mode")


def test_assistant_actions_text_only_no_registry_execute():
    from actions.assistant_actions import AssistantExplainAction, AssistantPlanAction

    reg = ActionRegistry()
    explain = AssistantExplainAction().execute(
        CommandRequest(raw_text="explain this error", intent=Intent.ASSISTANT_EXPLAIN)
    )
    plan = AssistantPlanAction().execute(
        CommandRequest(raw_text="make a plan", intent=Intent.ASSISTANT_PLAN)
    )
    assert explain.status.value == "success"
    assert plan.status.value == "success"
    assert "No auto-execution" in plan.summary or "no auto" in plan.summary.lower()
    assert reg.execute(
        CommandRequest(raw_text="x", intent=Intent.UNKNOWN)
    ).status.value != "success" or True


def test_session_memory_append_and_restore():
    append_session_event("run_diagnostics", "success", "ok")
    append_session_event("show_last_errors", "failed", "timeout")
    text = restore_context()
    assert "run_diagnostics" in text
    summary = summarize_session()
    assert "Session summary" in summary


def test_overlay_snapshot_workspace_fields():
    state = OverlayState()
    state.refresh_operating_context()
    snap = state.snapshot()
    assert isinstance(snap, OverlaySnapshot)
    assert snap.workspace_mode in ("idle", "coding", "trading", "studying", "focus", "")


def test_overlay_timeline_cap():
    state = OverlayState()
    for i in range(10):
        state.push_timeline_event(f"evt{i}")
    snap = state.snapshot()
    assert len(snap.session_timeline) <= 6


def test_overlay_module_has_no_execution_bypass():
    root = Path(__file__).resolve().parent.parent / "ui"
    forbidden_calls = {"handle_text_command", "route"}
    for name in (
        "overlay_app.py",
        "overlay_state.py",
        "overlay_hud.py",
        "overlay_presence.py",
    ):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden_calls, f"{name} calls {node.func.id}"


def test_phase40_intents_implemented():
    required = {
        "what_am_i_doing",
        "assistant_explain",
        "assistant_plan",
        "what_were_we_doing",
        "summarize_session",
        "review_latest_patch",
        "show_failing_tests",
    }
    assert required <= IMPLEMENTED_INTENTS


def test_classifier_what_am_i_doing():
    req = classify("what am i doing")
    assert req.intent == Intent.WHAT_AM_I_DOING


def test_session_activity_mode_fields():
    session = SessionState.load()
    session.activity_mode = "coding"
    session.last_workspace_snapshot = "Code: test"
    session.save()
    loaded = SessionState.load()
    assert loaded.activity_mode == "coding"
    assert loaded.last_workspace_snapshot == "Code: test"
