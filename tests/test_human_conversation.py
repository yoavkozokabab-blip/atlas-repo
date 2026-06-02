"""Human conversation runtime — barge-in, memory window, follow-ups, streaming."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_interrupt_on_user_speech_start_under_target_ms(monkeypatch):
    from voice.human_conversation import (
        get_last_barge_in_cancel_ms,
        interrupt_on_user_speech_start,
        reset_human_conversation_for_tests,
    )

    reset_human_conversation_for_tests()
    monkeypatch.setattr(
        "voice.streaming_player.pause_playback_immediately",
        lambda: None,
    )
    monkeypatch.setattr("voice.streaming_player.request_stop_speaking", lambda: None)
    monkeypatch.setattr("voice.streaming_player.is_speaking", lambda: False)
    monkeypatch.setattr("voice.realtime_tts.cancel_active_speech", lambda: True)
    monkeypatch.setattr("config.HUMAN_BARGE_IN_TARGET_MS", 200.0, raising=False)

    assert interrupt_on_user_speech_start(partial_text="hi") is True
    cancel_ms = get_last_barge_in_cancel_ms()
    assert cancel_ms is not None
    assert cancel_ms < 200.0


def test_active_tts_barge_in_under_target_ms(monkeypatch):
    """Prove cancel latency with simulated active playback + provider cancel."""
    import time

    from voice import streaming_player
    from voice.human_conversation import (
        get_last_barge_in_cancel_ms,
        interrupt_on_user_speech_start,
        reset_human_conversation_for_tests,
    )
    from voice.realtime_tts import (
        register_active_cancel_for_tests,
        reset_realtime_tts_for_tests,
    )

    reset_human_conversation_for_tests()
    reset_realtime_tts_for_tests()
    monkeypatch.setattr("config.HUMAN_BARGE_IN_TARGET_MS", 200.0, raising=False)
    monkeypatch.setattr(
        "voice.streaming_player.pause_playback_immediately",
        lambda: None,
    )
    monkeypatch.setattr("voice.streaming_player.request_stop_speaking", lambda: None)

    cancel_calls: list[float] = []

    def _fake_provider_cancel() -> None:
        cancel_calls.append(time.perf_counter())

    register_active_cancel_for_tests(_fake_provider_cancel)
    streaming_player._speaking.set()

    assert interrupt_on_user_speech_start(partial_text="user talking") is True
    assert cancel_calls, "active provider cancel must run"
    cancel_ms = get_last_barge_in_cancel_ms()
    assert cancel_ms is not None
    assert cancel_ms < 200.0, f"barge-in cancel_ms={cancel_ms:.1f} exceeded 200ms target"
    streaming_player._speaking.clear()
    reset_realtime_tts_for_tests()


def test_conversation_memory_window_twenty_turns(monkeypatch, tmp_path):
    import json

    from conversation.context_store import (
        append_turn,
        get_recent_turns,
        reset_conversation_store,
    )

    path = tmp_path / "conversation_context.json"
    monkeypatch.setattr("config.CONVERSATION_CONTEXT_PATH", path, raising=False)
    monkeypatch.setattr("conversation.context_store.CONVERSATION_CONTEXT_PATH", path)
    monkeypatch.setattr("config.CONVERSATION_MAX_TURNS", 20, raising=False)
    monkeypatch.setattr("conversation.context_store.CONVERSATION_MAX_TURNS", 20)
    monkeypatch.setattr("config.CONVERSATION_ENABLED", True, raising=False)
    reset_conversation_store()

    for i in range(25):
        append_turn(
            raw_text=f"user turn {i}",
            intent="unknown",
            status="success",
            summary=f"assistant {i}",
            input_mode="voice",
        )

    turns = get_recent_turns(limit=25)
    assert len(turns) == 20
    assert "user turn 24" in (turns[-1].raw_text_excerpt or "")


def test_follow_up_compare_it_to_nvidia():
    from conversation.follow_up_resolver import resolve_follow_up_text

    with (
        patch(
            "conversation.semantic_stream.reformulation.reformulate_with_context",
            return_value=("", ""),
        ),
        patch(
            "conversation.follow_up_resolver._last_intent",
            return_value="compare_live_vs_backtest",
        ),
        patch(
            "conversation.follow_up_resolver._last_assistant_summary",
            return_value="live vs backtest",
        ),
    ):
        text, reason = resolve_follow_up_text("compare it to Nvidia")
    assert reason == "continuation_compare"
    assert "nvidia" in text.lower()


def test_follow_up_tell_me_more():
    from conversation.follow_up_resolver import resolve_follow_up_text

    with (
        patch(
            "conversation.semantic_stream.reformulation.reformulate_with_context",
            return_value=("", ""),
        ),
        patch(
            "conversation.follow_up_resolver._last_assistant_summary",
            return_value="open positions summary",
        ),
    ):
        text, reason = resolve_follow_up_text("tell me more")
    assert reason == "continuation_tell_more"
    assert "open positions" in text.lower()


def test_follow_up_what_about_second_one():
    from conversation.context_store import ConversationTurn
    from conversation.follow_up_resolver import resolve_follow_up_text

    turns = [
        ConversationTurn(
            timestamp="t1",
            intent="a",
            status="success",
            raw_text_excerpt="first topic",
            summary_excerpt="",
        ),
        ConversationTurn(
            timestamp="t2",
            intent="b",
            status="success",
            raw_text_excerpt="second topic here",
            summary_excerpt="",
        ),
    ]
    with patch(
        "conversation.context_store.get_recent_turns",
        return_value=turns,
    ):
        text, reason = resolve_follow_up_text("what about the second one?")
    assert reason == "ordinal_second"
    assert "second topic" in text


def test_llm_streaming_early_clause_chunk(monkeypatch):
    from conversation.llm_streaming import _yield_speakable_chunks

    monkeypatch.setattr("config.CONVERSATION_STREAM_FIRST_CHUNK_CHARS", 10, raising=False)
    ready, rest = _yield_speakable_chunks(
        "Hello there, this is a longer answer",
        first_chunk=True,
    )
    assert ready
    assert ready[0] == "Hello there,"


def test_classify_expands_follow_up_before_rules(monkeypatch):
    from conversation.follow_up_resolver import resolve_follow_up_text

    with (
        patch(
            "conversation.semantic_stream.reformulation.reformulate_with_context",
            return_value=("", ""),
        ),
        patch(
            "conversation.follow_up_resolver._last_assistant_summary",
            return_value="dashboard health",
        ),
    ):
        expanded, reason = resolve_follow_up_text("tell me more")
    assert reason == "continuation_tell_more"
    assert expanded != "tell me more"
