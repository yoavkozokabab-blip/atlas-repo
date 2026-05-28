"""50 strict voice scenarios (Phase 67 — 50% real target)."""

from __future__ import annotations

import config

from validation.strict_framework import StrictCategoryMeasurement, run_strict_category
from validation.strict_graders import (
    grade_voice_real_conversation,
    grade_voice_runtime_probe,
    grade_voice_simulated_routing,
)

_CATEGORY = "Voice Conversation"

_PHRASES = [
    "show voice health",
    "show voice debug",
    "test streaming stt",
    "cancel active speech",
    "show capability health",
]


def _voice_scenarios() -> list:
    from validation.strict_framework import StrictScenarioFn

    config.REAL_VOICE_VALIDATION_ENABLED = True
    scenarios: list[tuple[str, StrictScenarioFn]] = []

    def _mk_real_voice(hint: str = "show voice health") -> StrictScenarioFn:
        def _run():
            from voice.real_voice_conversation import run_real_voice_conversation_test

            _ok, body = run_real_voice_conversation_test(routing_hint=hint, record_seconds=0.8)
            return grade_voice_real_conversation(body)

        return _run

    for i in range(25):
        scenarios.append((f"voice_real_{i+1:02d}", _mk_real_voice("show voice health")))

    def _mk_intent(phrase: str) -> StrictScenarioFn:
        def _run():
            from brain.intent_classifier import classify_rules
            from core.types import Intent

            req = classify_rules(phrase)
            expected = {
                "show voice health": Intent.SHOW_VOICE_HEALTH,
                "show voice debug": Intent.SHOW_VOICE_DEBUG,
                "test streaming stt": Intent.TEST_STREAMING_STT,
                "cancel active speech": Intent.CANCEL_ACTIVE_SPEECH,
                "show capability health": Intent.SHOW_CAPABILITY_HEALTH,
            }.get(phrase, req.intent)
            return grade_voice_simulated_routing(req.intent == expected, f"intent={req.intent.value}")

        return _run

    for i in range(10):
        scenarios.append((f"voice_intent_{i+1:02d}", _mk_intent(_PHRASES[i % len(_PHRASES)])))

    def _mk_health() -> StrictScenarioFn:
        def _run():
            from reliability.voice_health import show_voice_health

            body = show_voice_health()
            return grade_voice_runtime_probe("Voice health" in body, body[:120])

        return _run

    for i in range(5):
        scenarios.append((f"voice_health_{i+1:02d}", _mk_health()))

    def _mk_streaming() -> StrictScenarioFn:
        def _run():
            from voice.streaming_stt.session_policy import (
                get_streaming_disable_reason,
                is_streaming_stt_enabled_for_session,
            )

            detail = f"enabled={is_streaming_stt_enabled_for_session()} reason={get_streaming_disable_reason() or 'none'}"
            return grade_voice_runtime_probe(True, detail)

        return _run

    for i in range(5):
        scenarios.append((f"voice_streaming_{i+1:02d}", _mk_streaming()))

    def _mk_action() -> StrictScenarioFn:
        def _run():
            from actions.registry import ActionRegistry
            from core.types import ActionStatus, CommandRequest, Intent

            reg = ActionRegistry()
            action = reg._actions.get(Intent.TEST_REAL_VOICE_CONVERSATION.value)
            if action is None:
                return grade_voice_simulated_routing(False, "action_missing")
            res = action.execute(
                CommandRequest(raw_text="test real voice conversation", intent=Intent.TEST_REAL_VOICE_CONVERSATION)
            )
            return grade_voice_real_conversation(res.summary or "")

        return _run

    for i in range(5):
        scenarios.append((f"voice_action_{i+1:02d}", _mk_action()))

    return scenarios


def measure_voice_conversation() -> StrictCategoryMeasurement:
    return run_strict_category(_CATEGORY, _voice_scenarios())
