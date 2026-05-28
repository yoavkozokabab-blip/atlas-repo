"""Computer control foundation tests."""

from unittest.mock import MagicMock, patch

import pytest

from actions.computer_control_actions import (
    CopyTextToClipboardAction,
    FocusWindowAction,
    GetClipboardSummaryAction,
    GetFocusedAppAction,
)
from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from config import CONFIRMATION_REQUIRED_INTENTS, COMPUTER_CONTROL_DISABLED_MESSAGE
from core.types import ActionStatus, CommandRequest, Intent
from computer_control.models import WindowActionResult
from computer_control.safety import (
    ComputerControlSafetyError,
    ensure_control_enabled,
    summarize_clipboard_text,
    validate_clipboard_write,
)


@pytest.fixture
def control_on(monkeypatch):
    monkeypatch.setattr("config.COMPUTER_CONTROL_ENABLED", True)


@pytest.fixture
def control_off(monkeypatch):
    monkeypatch.setattr("config.COMPUTER_CONTROL_ENABLED", False)


def test_confirm_required_intents():
    for name in (
        "focus_window",
        "copy_text_to_clipboard",
        "clear_clipboard",
        "minimize_window",
        "maximize_window",
    ):
        assert name in CONFIRMATION_REQUIRED_INTENTS
    assert "get_focused_app" not in CONFIRMATION_REQUIRED_INTENTS


def test_hebrew_mappings():
    assert classify_rules("איזה אפליקציה בפוקוס").intent == Intent.GET_FOCUSED_APP
    assert classify_rules("מה יש בקליפבורד").intent == Intent.GET_CLIPBOARD_SUMMARY
    req = classify_rules("תעביר פוקוס לכרום")
    assert req.intent == Intent.FOCUS_WINDOW
    assert "chrome" in req.params.get("title", "").lower() or "כרום" in req.params.get("title", "")


def test_control_disabled_blocks(control_off):
    from computer_control.safety import ComputerControlDisabledError

    with pytest.raises(ComputerControlDisabledError):
        ensure_control_enabled()
    result = GetFocusedAppAction().execute(
        CommandRequest(raw_text="x", intent=Intent.GET_FOCUSED_APP)
    )
    assert result.status == ActionStatus.BLOCKED
    assert COMPUTER_CONTROL_DISABLED_MESSAGE in result.summary


def test_read_only_focused_app_mocked(control_on, monkeypatch):
    from computer_control.models import FocusedAppInfo

    monkeypatch.setattr(
        "actions.computer_control_actions.get_focused_app",
        lambda: FocusedAppInfo(title="Cursor", width=800, height=600),
    )
    result = GetFocusedAppAction().execute(
        CommandRequest(raw_text="x", intent=Intent.GET_FOCUSED_APP)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "Cursor" in result.summary


def test_router_focus_requires_confirmation(control_on):
    router = CommandRouter()
    result = router.route("focus window Chrome")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED


def test_multiple_windows_clarifies(control_on, monkeypatch):
    monkeypatch.setattr(
        "actions.computer_control_actions.focus_window",
        lambda title: WindowActionResult(
            success=False,
            message="Multiple windows match",
            ambiguous=True,
            candidates=["Chrome A", "Chrome B"],
        ),
    )
    result = FocusWindowAction().execute(
        CommandRequest(
            raw_text="focus window Chrome",
            intent=Intent.FOCUS_WINDOW,
            params={"title": "Chrome"},
            confirmed=True,
        )
    )
    assert result.status == ActionStatus.CLARIFICATION_NEEDED
    assert "Chrome A" in result.summary or "Candidates" in result.summary


def test_clipboard_redacts_secrets():
    raw = "api_key=secret123 token=abc"
    text, truncated = summarize_clipboard_text(raw)
    assert "secret123" not in text
    assert truncated is False or len(text) <= 1003


def test_copy_blocks_secrets(control_on):
    with pytest.raises(ComputerControlSafetyError):
        validate_clipboard_write("password=mysecret")
    result = CopyTextToClipboardAction().execute(
        CommandRequest(
            raw_text="copy",
            intent=Intent.COPY_TEXT_TO_CLIPBOARD,
            params={"text": "api_key=bad"},
        )
    )
    assert result.status == ActionStatus.BLOCKED


def test_get_clipboard_summary_mocked(control_on, monkeypatch):
    from computer_control.models import ClipboardSummary

    monkeypatch.setattr(
        "actions.computer_control_actions.get_clipboard_summary",
        lambda: ClipboardSummary(text="hello", length=5),
    )
    result = GetClipboardSummaryAction().execute(
        CommandRequest(raw_text="x", intent=Intent.GET_CLIPBOARD_SUMMARY)
    )
    assert result.status == ActionStatus.SUCCESS


def test_no_click_type_hotkey_in_package():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "computer_control"
    forbidden = (
        "pyautogui",
        "pynput",
        "click(",
        "type_text",
        "press_key",
        "hotkey",
        "send_keys",
        "mouse.",
        "drag(",
        "scroll(",
    )
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{token} in {path.name}"


def test_no_coordinate_click_actions():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "computer_control"
    banned = ("moveto", "move_to", "click(", ".click", "position()")
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in text, f"{token} in {path.name}"


def test_actions_use_registry_path(control_on, monkeypatch):
    """RunWorkflow-style: action calls computer_control module, router wraps security."""
    from computer_control.models import FocusedAppInfo

    monkeypatch.setattr(
        "actions.computer_control_actions.get_focused_app",
        lambda: FocusedAppInfo(title="App"),
    )
    router = CommandRouter()
    result = router.route("get focused app")
    assert result.status == ActionStatus.SUCCESS
