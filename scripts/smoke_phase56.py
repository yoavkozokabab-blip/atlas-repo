"""Smoke test for Phase 56 real-time conversational runtime."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.phase56_actions import simulate_barge_in_for_tests
from actions.registry import ActionRegistry
from assistant.conversation_state import reset_conversation_state_for_tests
from brain.intent_classifier import classify_rules
from brain.operational_command_phrases import match_operational_priority_commands
from brain.realtime_understanding import predict_intent
from core.intent_validation import run_startup_intent_validation, validate_phase56_runtime_wiring
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from runtime.background_tasks import reset_background_engine_for_tests
from voice.interruption_manager import reset_interruption_manager_for_tests
from voice.streaming_pipeline import get_streaming_pipeline, reset_streaming_pipeline_for_tests


def _setup_isolated_data(tmp: Path) -> None:
    import config

    config.DATA_DIR = tmp / "data"
    import assistant.conversation_state as cs

    cs.CONVERSATION_STATE_PATH = config.DATA_DIR / "conversation_state.json"
    import assistant.proactive_assistant as pa

    pa.PROACTIVE_PATH = config.DATA_DIR / "proactive_assistant.json"


def _assert_intent(phrase: str, expected: Intent) -> None:
    op = match_operational_priority_commands(phrase)
    rules = classify_rules(phrase)
    for label, req in (("operational", op), ("rules", rules)):
        assert req is not None, (phrase, label)
        assert req.intent == expected, (phrase, label, req.intent, expected)
    print(f"OK classify {phrase!r} -> {expected.value}")


def _run_action(registry: ActionRegistry, phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, (phrase, getattr(gate, "summary", gate))
    result = registry.execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    assert "not implemented" not in result.summary.lower(), result.summary
    print(f"OK action {phrase!r}")
    return result.summary


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    print("OK startup validation")

    wiring = validate_phase56_runtime_wiring()
    assert not wiring, [i.format() for i in wiring]
    print("OK phase56 runtime wiring")

    for phrase, intent in (
        ("what are we discussing", Intent.WHAT_ARE_WE_DISCUSSING),
        ("summarize current conversation", Intent.SUMMARIZE_CURRENT_CONVERSATION),
        ("resume previous topic", Intent.RESUME_PREVIOUS_TOPIC),
        ("start continuous listening", Intent.START_CONTINUOUS_LISTENING),
        ("stop continuous listening", Intent.STOP_CONTINUOUS_LISTENING),
        ("explain this project", Intent.EXPLAIN_THIS_PROJECT),
        ("explain architecture", Intent.EXPLAIN_ARCHITECTURE),
        ("show project intelligence", Intent.SHOW_PROJECT_INTELLIGENCE),
        ("propose engineering patch", Intent.PROPOSE_ENGINEERING_PATCH),
        ("simulate engineering patch", Intent.SIMULATE_ENGINEERING_PATCH),
        ("show proactive suggestions", Intent.SHOW_PROACTIVE_SUGGESTIONS),
        ("show realtime runtime", Intent.SHOW_REALTIME_RUNTIME),
        ("phase 56 status", Intent.PHASE56_STATUS),
    ):
        _assert_intent(phrase, intent)

    tmp = Path(tempfile.mkdtemp()) / "phase56"
    _setup_isolated_data(tmp)
    reset_conversation_state_for_tests()
    reset_interruption_manager_for_tests()
    reset_streaming_pipeline_for_tests()
    reset_background_engine_for_tests()

    registry = ActionRegistry()

    _run_action(registry, "start continuous listening", Intent.START_CONTINUOUS_LISTENING)
    pipe = get_streaming_pipeline()
    pipe.push_partial("Jarvis open the browser please")
    prediction = predict_intent("Jarvis open the browser please")
    assert prediction is not None, "prediction missing"
    assert prediction.intent, prediction
    print("OK mid-sentence intent prediction")

    barge = simulate_barge_in_for_tests(speaking_text="This is a long JARVIS response being interrupted.")
    assert "preserved=True" in barge or "paused_chars=" in barge, barge
    print(f"OK barge-in simulation: {barge}")

    _run_action(registry, "what are we discussing", Intent.WHAT_ARE_WE_DISCUSSING)
    _run_action(registry, "summarize current conversation", Intent.SUMMARIZE_CURRENT_CONVERSATION)
    _run_action(registry, "explain this project", Intent.EXPLAIN_THIS_PROJECT)
    _run_action(registry, "explain architecture", Intent.EXPLAIN_ARCHITECTURE)
    _run_action(registry, "propose engineering patch", Intent.PROPOSE_ENGINEERING_PATCH)
    _run_action(registry, "show proactive suggestions", Intent.SHOW_PROACTIVE_SUGGESTIONS)
    _run_action(registry, "show realtime runtime", Intent.SHOW_REALTIME_RUNTIME)
    _run_action(registry, "stop continuous listening", Intent.STOP_CONTINUOUS_LISTENING)

    with patch("voice.speech_controller.barge_in_if_speaking", return_value=True):
        for phrase in (
            "what are we discussing",
            "summarize current conversation",
            "show conversation state",
        ):
            summary = _run_action(registry, phrase, Intent.WHAT_ARE_WE_DISCUSSING if "discussing" in phrase else (
                Intent.SUMMARIZE_CURRENT_CONVERSATION if "summarize" in phrase else Intent.SHOW_CONVERSATION_STATE
            ))
            assert summary

    status = _run_action(registry, "phase 56 status", Intent.PHASE56_STATUS)
    assert "Phase 56" in status, status
    print("OK rapid back-and-forth conversation commands")

    print("SMOKE PASS phase56")


if __name__ == "__main__":
    main()
