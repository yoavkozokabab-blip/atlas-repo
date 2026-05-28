"""Phase 65 product hardening wiring tests."""

from __future__ import annotations

import pytest

from actions.registry import ActionRegistry
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent


@pytest.mark.parametrize(
    "text,intent",
    [
        ("show voice health", Intent.SHOW_VOICE_HEALTH),
        ("repair memory store", Intent.REPAIR_MEMORY_STORE),
        ("show browser health", Intent.SHOW_BROWSER_HEALTH),
        ("show system health", Intent.SHOW_SYSTEM_HEALTH),
        ("show performance report", Intent.SHOW_PERFORMANCE_REPORT),
        ("summarize my inbox", Intent.SUMMARIZE_MY_INBOX),
        ("show urgent emails", Intent.SHOW_URGENT_EMAILS),
        ("summarize my calendar", Intent.SUMMARIZE_MY_CALENDAR),
    ],
)
def test_phase65_intents(text: str, intent: Intent):
    assert classify_rules(text).intent == intent


def test_phase65_actions_registered():
    reg = ActionRegistry()
    for intent in (
        Intent.SHOW_VOICE_HEALTH,
        Intent.REPAIR_MEMORY_STORE,
        Intent.SHOW_BROWSER_HEALTH,
        Intent.SHOW_SYSTEM_HEALTH,
        Intent.SHOW_PERFORMANCE_REPORT,
        Intent.SUMMARIZE_MY_INBOX,
    ):
        assert reg.has(intent.value)


def test_show_system_health_action():
    reg = ActionRegistry()
    action = reg._actions[Intent.SHOW_SYSTEM_HEALTH.value]
    result = action.execute(CommandRequest(raw_text="show system health", intent=Intent.SHOW_SYSTEM_HEALTH))
    assert "runtime_health_score" in result.summary
