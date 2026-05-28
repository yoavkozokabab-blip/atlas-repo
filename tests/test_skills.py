"""Skill system tests."""

from unittest.mock import MagicMock, patch

import pytest

from actions.registry import ActionRegistry
from actions.capabilities import HelpForCommandAction, ExplainSkillAction, ShowCapabilitiesAction
from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS
from core.types import CommandRequest, Intent
from skills.base import SkillPermissionLevel, permission_for_intent
from skills.registry import SkillRegistry, SkillRegistryError, get_skill_registry, reset_skill_registry
from skills.trading_skill import TradingSkill


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_skill_registry()
    yield
    reset_skill_registry()


def test_all_skill_actions_map_to_allowlisted_intents():
    reg = get_skill_registry()
    for act in reg.list_actions():
        assert act.intent == act.name
        assert act.intent in IMPLEMENTED_INTENTS or act.intent in {
            "show_capabilities",
            "list_skills",
            "explain_skill",
            "help_for_command",
        }


def test_confirm_required_actions_marked_correctly():
    reg = get_skill_registry()
    for act in reg.list_actions():
        if act.intent in CONFIRMATION_REQUIRED_INTENTS:
            assert act.permission_level == SkillPermissionLevel.CONFIRM_REQUIRED
        elif act.intent in IMPLEMENTED_INTENTS:
            assert act.permission_level in (
                SkillPermissionLevel.READ_ONLY,
                SkillPermissionLevel.CONFIRM_REQUIRED,
            )


def test_show_capabilities_returns_groups():
    action = ShowCapabilitiesAction()
    result = action.execute(CommandRequest(raw_text="capabilities", intent=Intent.SHOW_CAPABILITIES))
    assert result.status.value == "success"
    assert "Trading" in result.summary
    assert "Logs" in result.summary
    assert "Code search" in result.summary
    assert "Voice / TTS" in result.summary
    assert "Vision" in result.summary
    assert "Diagnostics" in result.summary
    assert "Workflows" in result.summary
    assert "Services" in result.summary
    assert "Computer control" in result.summary


def test_explain_skill_hebrew_trading_alias():
    action = ExplainSkillAction()
    result = action.execute(
        CommandRequest(
            raw_text="איזה פקודות מסחר יש",
            intent=Intent.EXPLAIN_SKILL,
            params={"skill": "trading"},
        )
    )
    assert result.status.value == "success"
    assert "trading" in result.summary.lower() or "Trading" in result.summary
    assert "run_live_daily_loop" in result.summary


def test_help_for_command_daily_loop_confirmation():
    action = HelpForCommandAction()
    result = action.execute(
        CommandRequest(
            raw_text="help run daily loop",
            intent=Intent.HELP_FOR_COMMAND,
            params={"query": "run live daily loop"},
        )
    )
    assert result.status.value == "success"
    assert "run_live_daily_loop" in result.summary
    assert "Confirmation required" in result.summary


def test_registry_rejects_duplicate_action_names():
    from skills.base import SkillAction, SkillMetadata, action

    reg = SkillRegistry()
    dup = action("open_cursor", "duplicate test")
    reg.register_skill(
        SkillMetadata(name="skill_a", description="a", category="Test", actions=[dup])
    )
    with pytest.raises(SkillRegistryError, match="Duplicate skill action"):
        reg.register_skill(
            SkillMetadata(name="skill_b", description="b", category="Test", actions=[dup])
        )


def test_no_skill_direct_execution_bypass():
    """SkillAction.handler is intent name only — capabilities do not run trading handlers."""
    reg = get_skill_registry()
    act = reg.get_action("run_live_daily_loop")
    assert act is not None
    assert act.handler == "run_live_daily_loop"
    assert not callable(act.handler)

    with patch("actions.trading_loop.RunLiveDailyLoopAction.execute") as run_loop:
        ShowCapabilitiesAction().execute(
            CommandRequest(raw_text="x", intent=Intent.SHOW_CAPABILITIES)
        )
        run_loop.assert_not_called()


def test_validate_skill_action():
    reg = get_skill_registry()
    act = reg.validate_skill_action("show_last_errors")
    assert act.intent == "show_last_errors"


def test_classify_show_capabilities():
    from brain.intent_classifier import classify

    req = classify("מה אתה יודע לעשות")
    assert req.intent == Intent.SHOW_CAPABILITIES


def test_permission_for_unimplemented_is_blocked():
    assert permission_for_intent("open_task_manager") == SkillPermissionLevel.BLOCKED
