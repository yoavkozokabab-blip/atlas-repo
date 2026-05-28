"""Ensure CommandResult structure is consistent."""

from actions.registry import ActionRegistry
from core.types import ActionStatus, CommandRequest, CommandResult, Intent


def test_command_result_model_fields():
    r = CommandResult(
        intent=Intent.OPEN_CURSOR,
        status=ActionStatus.SUCCESS,
        summary="ok",
        data={"x": 1},
        error=None,
        requires_confirmation=False,
        confirmation_id=None,
        next_suggestions=["a"],
    )
    assert r.summary == "ok"
    assert r.message == "ok"
    assert r.status == ActionStatus.SUCCESS


def test_registry_actions_return_structured_result():
    from approvals.inbox import reset_inbox_store
    from core import confirmation

    confirmation.clear_all()
    reset_inbox_store()
    registry = ActionRegistry()
    skip_router_delegate = frozenset(
        {
            Intent.APPROVE_PENDING_ACTION.value,
            Intent.REJECT_PENDING_ACTION.value,
            Intent.RUN_WORKFLOW.value,
        }
    )
    for intent_name, action in registry._actions.items():
        if intent_name in skip_router_delegate:
            continue
        req = CommandRequest(
            raw_text="test",
            intent=Intent(intent_name),
            confidence=1.0,
        )
        result = action.execute(req)
        assert isinstance(result, CommandResult)
        assert result.intent == Intent(intent_name)
        assert isinstance(result.status, ActionStatus)
        assert isinstance(result.summary, str)
        assert isinstance(result.data, dict)
        assert isinstance(result.next_suggestions, list)
