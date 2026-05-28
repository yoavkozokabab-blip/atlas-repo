"""Phase 59.6 — session handoff must not fail on phrase-table unpack errors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.types import ActionStatus, CommandResult, Intent
from voice.streaming_stt.stream_session import StreamingSttResult


def test_phrase_rules_rows_are_three_tuples():
    from brain.intent_classifier import _PHRASE_RULES
    from core.intent_validation import validate_phrase_table_row_lengths

    issues = validate_phrase_table_row_lengths(
        _PHRASE_RULES,
        source="intent_classifier",
        expected_len=3,
    )
    assert issues == []


def test_classify_rules_does_not_raise_unpack_on_any_phrase():
    from brain.intent_classifier import _PHRASE_RULES, classify_rules

    # Exercises the full phrase-table scan (where the 2-tuple bug surfaced).
    assert classify_rules("hello jarvis").intent in {Intent.UNKNOWN, Intent.CLARIFY}
    assert classify_rules("test direct tts").intent == Intent.TEST_DIRECT_TTS
    for phrases, _intent, _confidence in _PHRASE_RULES:
        for phrase in phrases[:1]:
            classify_rules(phrase)  # must not raise ValueError on unpack


def test_process_human_turn_routes_without_unpack_error():
    from conversation.human_runtime import _process_human_turn, reset_human_runtime_for_tests

    reset_human_runtime_for_tests()
    app = MagicMock()
    app.handle_text_command.return_value = CommandResult(
        intent=Intent.UNKNOWN,
        status=ActionStatus.SUCCESS,
        summary="ok",
    )
    with patch(
        "conversation.human_runtime.handle_conversational_turn",
        return_value={"text": "hi", "provider": "mock"},
    ):
        assert _process_human_turn("what is the weather", app=app) is True
    app.handle_text_command.assert_not_called()


def test_wakeword_to_human_session_handoff_end_to_end():
    import config as cfg
    from conversation.human_runtime import (
        enable_human_conversational_runtime,
        reset_human_runtime_for_tests,
        run_human_conversation_session,
        should_start_human_session_after_wake,
    )
    from voice.continuous_mic import reset_continuous_mic_for_tests
    from voice.streaming_stt.session_policy import reset_streaming_session

    cfg.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = True
    cfg.CONVERSATION_CONTINUOUS_MIC_ENABLED = True
    cfg.CONVERSATION_SESSION_IDLE_SECONDS = 1.0
    cfg.STT_STREAMING_BUFFER_ENABLED = True
    reset_streaming_session()
    reset_human_runtime_for_tests()
    reset_continuous_mic_for_tests()
    enable_human_conversational_runtime()

    app = MagicMock()
    app.session = None
    app.handle_text_command.return_value = CommandResult(
        intent=Intent.UNKNOWN,
        status=ActionStatus.SUCCESS,
        summary="Handled",
    )
    assert should_start_human_session_after_wake(app)

    turn_queue = [
        StreamingSttResult(
            text="what time is it",
            partial_updates=1,
            decode_ms=10.0,
            record_seconds=1.0,
            endpoint_silence_ms=400.0,
        ),
        StreamingSttResult(
            text="stop listening",
            partial_updates=0,
            decode_ms=5.0,
            record_seconds=0.5,
            endpoint_silence_ms=400.0,
        ),
    ]

    def _mock_capture(*, on_partial=None, **kwargs):
        del kwargs
        item = turn_queue.pop(0) if turn_queue else StreamingSttResult(
            text="",
            partial_updates=0,
            decode_ms=0.0,
            record_seconds=0.0,
            endpoint_silence_ms=0.0,
        )
        if on_partial and item.partial_updates:
            on_partial("partial")
        return item

    with patch("voice.continuous_mic.capture_turn", side_effect=_mock_capture), patch(
        "conversation.human_runtime.handle_conversational_turn",
        return_value={"text": "now", "provider": "mock"},
    ):
        result = run_human_conversation_session(app=app)
    assert int(result.get("turns", 0)) >= 1
    assert int(result.get("partials", 0)) >= 1
