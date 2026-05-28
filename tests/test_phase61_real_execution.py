from __future__ import annotations

from core.types import CommandRequest, Intent


def test_phase61_intent_classification_rules() -> None:
    from brain.intent_classifier import classify_rules

    assert classify_rules("open browser").intent == Intent.OPEN_BROWSER
    assert classify_rules("test real browser").intent == Intent.TEST_REAL_BROWSER
    assert classify_rules("compare these pages").intent == Intent.COMPARE_THESE_PAGES
    assert classify_rules("what tab is active").intent == Intent.WHAT_TAB_IS_ACTIVE
    assert classify_rules("what page am i on").intent == Intent.WHAT_TAB_IS_ACTIVE
    assert classify_rules("summarize current page").intent == Intent.SUMMARIZE_THIS_PAGE


def test_phase61_actions_registered() -> None:
    from actions.registry import ActionRegistry

    reg = ActionRegistry()
    for intent in (
        Intent.OPEN_BROWSER,
        Intent.TEST_REAL_BROWSER,
        Intent.COMPARE_THESE_PAGES,
        Intent.WHAT_TAB_IS_ACTIVE,
    ):
        assert intent.value in reg._actions


def test_phase61_memory_semantic_search() -> None:
    from memory.store import get_personal_memory

    mem = get_personal_memory()
    mem.remember(
        "phase61 semantic retrieval target",
        category="project_context",
        tags=["phase61", "task:unit"],
        importance=0.9,
        confidence=0.9,
    )
    hits = mem.semantic_search("semantic retrieval")
    assert hits


def test_phase61_capability_orchestration() -> None:
    from runtime.capability_orchestrator import dependency_graph, propagate_health

    graph = dependency_graph()
    assert "operator_loop" in graph
    status = propagate_health({k: True for k in graph})
    assert status["operator_loop"] == "healthy"


def test_phase61_open_browser_action_executes() -> None:
    from actions.phase60_actions import OpenBrowserAction

    action = OpenBrowserAction()
    result = action.execute(CommandRequest(raw_text="open browser", intent=Intent.OPEN_BROWSER))
    assert result.summary
