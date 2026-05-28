"""Tests for security validation."""

from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent


def test_unknown_intent_blocked():
    req = CommandRequest(raw_text="x", intent=Intent.UNKNOWN)
    result = validate_intent(req)
    assert result is not None
    assert result.status == ActionStatus.BLOCKED


def test_not_implemented_intent():
    req = CommandRequest(raw_text="x", intent=Intent.OPEN_TASK_MANAGER)
    result = validate_intent(req)
    assert result is not None
    assert result.status == ActionStatus.NOT_IMPLEMENTED


def test_implemented_intent_passes():
    req = CommandRequest(raw_text="x", intent=Intent.OPEN_CURSOR)
    assert validate_intent(req) is None


def test_clarify_returns_clarification_needed():
    req = CommandRequest(raw_text="x", intent=Intent.CLARIFY)
    result = validate_intent(req)
    assert result is not None
    assert result.status == ActionStatus.CLARIFICATION_NEEDED
