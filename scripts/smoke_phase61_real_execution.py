"""Phase 61 integrated smoke for real capability execution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(intent_name: str, text: str):
    from actions.registry import ActionRegistry
    from core.types import CommandRequest, Intent

    reg = ActionRegistry()
    intent = getattr(Intent, intent_name)
    action = reg._actions.get(intent.value)
    assert action is not None, f"missing action for {intent.value}"
    return action.execute(CommandRequest(raw_text=text, intent=intent))


def main() -> None:
    # real browser navigation
    opened = _run("OPEN_BROWSER", "open browser")
    search = _run("SEARCH_WEB_FOR", "search web for phase 61 runtime orchestration")
    tab = _run("WHAT_TAB_IS_ACTIVE", "what tab is active")
    dbg = _run("SHOW_BROWSER_DEBUG", "show browser debug")
    assert opened.summary.strip()
    assert search.summary.strip()
    assert tab.summary.strip()
    assert "provider:" in dbg.summary

    # persistent memory recall
    from memory.store import get_personal_memory

    mem = get_personal_memory()
    mem.remember(
        "phase61 persistent memory recall marker",
        category="project_context",
        tags=["phase61", "task:smoke"],
        importance=0.9,
        confidence=0.9,
    )
    sem = mem.semantic_search("persistent memory recall marker")
    assert sem, "semantic recall failed"

    # conversational interruption + recovery
    from voice.conversational_runtime import barge_in_cancel, recover_conversation_timeout

    _ = barge_in_cancel()
    rec = recover_conversation_timeout(timeout_seconds=30.0)
    assert rec

    # runtime recovery + health truthfulness
    health = _run("SHOW_CAPABILITY_HEALTH", "show capability health")
    assert "streaming_runtime" in health.summary
    assert "tts_backend_verification" in health.summary

    # operator loop persistence (stateful components available)
    from runtime.capability_orchestrator import dependency_graph, propagate_health

    graph = dependency_graph()
    status = propagate_health(
        {
            "runtime_monitor": True,
            "audio_runtime": True,
            "wakeword": True,
            "tts_runtime": True,
            "browser_runtime": True,
            "memory_runtime": True,
            "tool_trust": True,
            "streaming_conversation": True,
            "operator_loop": True,
        }
    )
    assert graph and status.get("operator_loop") == "healthy"

    print("SMOKE PASS phase61_real_execution")


if __name__ == "__main__":
    main()

