from __future__ import annotations

from core.types import CommandRequest, Intent


def test_phase60_new_intents_classify() -> None:
    from brain.intent_classifier import classify_rules

    assert classify_rules("show browser debug").intent == Intent.SHOW_BROWSER_DEBUG
    assert classify_rules("search web for nvidia earnings").intent == Intent.SEARCH_WEB_FOR
    assert classify_rules("summarize my day").intent == Intent.SUMMARIZE_MY_DAY
    assert classify_rules("find calendar conflicts").intent == Intent.FIND_CALENDAR_CONFLICTS
    assert classify_rules("show memory debug").intent == Intent.SHOW_MEMORY_DEBUG
    assert classify_rules("show runtime config mismatches").intent == Intent.SHOW_RUNTIME_CONFIG_MISMATCHES
    assert classify_rules("show capability health").intent == Intent.SHOW_CAPABILITY_HEALTH


def test_phase60_actions_registered() -> None:
    from actions.registry import ActionRegistry

    reg = ActionRegistry()
    for intent in (
        Intent.SHOW_BROWSER_DEBUG,
        Intent.SEARCH_WEB_FOR,
        Intent.SUMMARIZE_THIS_PAGE,
        Intent.COMPARE_THESE_RESULTS,
        Intent.SUMMARIZE_MY_DAY,
        Intent.SUMMARIZE_MY_LAST_100_EMAILS,
        Intent.WHAT_NEEDS_MY_ATTENTION_TODAY,
        Intent.FIND_CALENDAR_CONFLICTS,
        Intent.SHOW_MEMORY_DEBUG,
        Intent.SHOW_RUNTIME_CONFIG_MISMATCHES,
        Intent.SHOW_CAPABILITY_HEALTH,
    ):
        assert intent.value in reg._actions


def test_phase60_mock_summary_output_sections() -> None:
    from actions.phase60_actions import SummarizeMyDayAction

    action = SummarizeMyDayAction()
    result = action.execute(CommandRequest(raw_text="summarize my day", intent=Intent.SUMMARIZE_MY_DAY))
    body = result.summary.lower()
    for section in ("urgent", "waiting_on_me", "schedule", "risks", "recommended_actions"):
        assert f"{section}:" in body
    assert "mock mode" in body
    assert "no real external access" in body
    assert "simulated output only" in body


def test_sensitive_memory_requires_confirmation() -> None:
    from actions.memory_actions import RememberFactAction

    action = RememberFactAction()
    req = CommandRequest(raw_text="remember that prod password is hunter2", intent=Intent.REMEMBER_FACT)
    result = action.execute(req)
    assert result.status.value == "confirmation_required"

