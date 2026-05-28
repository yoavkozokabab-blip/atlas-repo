"""Confirmation framework tests."""

from unittest.mock import patch

from brain.router import CommandRouter
from core import confirmation
from core.types import ActionStatus, Intent


def setup_function():
    confirmation.clear_all()


def test_confirmation_required_not_executed_immediately():
    router = CommandRouter()
    with patch("actions.powershell.subprocess.Popen") as popen:
        result = router.route("run live daily loop")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert result.requires_confirmation
    assert result.confirmation_id
    popen.assert_not_called()


def test_yes_executes_pending_action():
    router = CommandRouter()
    with patch("actions.powershell.subprocess.Popen") as popen:
        router.route("run live daily loop")
        result = router.route("yes")
    popen.assert_called()
    assert result.status in (ActionStatus.SUCCESS, ActionStatus.FAILED)


def test_no_cancels_pending():
    router = CommandRouter()
    router.route("shutdown jarvis")
    result = router.route("no")
    assert result.summary == "Action cancelled."
    assert confirmation.get_pending_confirmation() is None


def test_timeout_blocks_confirmation(monkeypatch):
    monkeypatch.setattr("core.confirmation.CONFIRMATION_TIMEOUT_SECONDS", 0)
    confirmation.create_confirmation("run_live_daily_loop", {"raw_text": "x"})
    assert confirmation.get_pending_confirmation() is None
