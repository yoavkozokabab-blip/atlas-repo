"""Urgent phase: sub-500ms voice response mode."""

from __future__ import annotations

import importlib
from unittest.mock import patch

from core.results import result_success
from core.session import SessionState
from core.types import CommandRequest, Intent


def _enable_instant(monkeypatch):
    monkeypatch.setenv("VOICE_LATENCY_MODE", "instant")
    monkeypatch.setenv("VOICE_RUNTIME_MODE", "")
    monkeypatch.setenv("VOICE_PROFILE", "balanced")
    monkeypatch.setenv("STT_MODEL", "medium")
    monkeypatch.setenv("STT_BEAM_SIZE", "5")
    monkeypatch.setenv("STT_MULTIPASS_ENABLED", "true")
    monkeypatch.setenv("STT_STACK_ENABLED", "true")
    monkeypatch.setenv("STT_RETRY_ON_UNKNOWN", "true")
    monkeypatch.setenv("STT_STREAMING_BUFFER_ENABLED", "false")
    monkeypatch.setenv("CONVERSATION_SEMANTIC_STREAM_ENABLED", "false")
    monkeypatch.setenv("STT_PARTIAL_INTERVAL_MS", "500")
    monkeypatch.setenv("STT_STREAM_MIN_PARTIAL_CONTEXT_MS", "500")
    monkeypatch.setenv("STT_STREAM_ENDPOINT_SILENCE_MS", "900")
    import config

    return importlib.reload(config)


def test_instant_mode_overrides_heavy_stt(monkeypatch):
    cfg = _enable_instant(monkeypatch)

    assert cfg.VOICE_LATENCY_INSTANT is True
    assert cfg.STT_MODEL in {"base", "tiny"}
    assert cfg.STT_BEAM_SIZE == 1
    assert cfg.STT_MULTIPASS_ENABLED is False
    assert cfg.STT_STACK_ENABLED is False
    assert cfg.STT_RETRY_ON_UNKNOWN is False
    assert cfg.STT_STREAMING_BUFFER_ENABLED is True
    assert cfg.CONVERSATION_SEMANTIC_STREAM_ENABLED is True
    assert 1.5 <= cfg.STT_ROLLING_BUFFER_SECONDS <= 2.5
    assert 150 <= cfg.STT_PARTIAL_INTERVAL_MS <= 250
    assert 150 <= cfg.STT_STREAM_MIN_PARTIAL_CONTEXT_MS <= 250
    assert 350 <= cfg.STT_STREAM_ENDPOINT_SILENCE_MS <= 500


def test_fast_lane_does_not_execute_partials(monkeypatch):
    _enable_instant(monkeypatch)
    from brain.instant_fast_lane import match_instant_fast_lane

    with patch("actions.registry.ActionRegistry.execute") as execute:
        req = match_instant_fast_lane("open dashboard")

    assert req is not None
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD
    assert req.confidence >= 0.85
    execute.assert_not_called()


def test_final_fast_lane_command_routes_normally(monkeypatch, tmp_path):
    _enable_instant(monkeypatch)
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", tmp_path / "history.jsonl", raising=False)
    from brain.router import CommandRouter

    router = CommandRouter(session=SessionState())
    with (
        patch("brain.router.validate_intent", return_value=None) as validate,
        patch.object(
            router.registry,
            "execute",
            return_value=result_success(Intent.OPEN_TRADING_DASHBOARD, "Dashboard routed."),
        ) as execute,
        patch.object(router, "_finalize"),
    ):
        result = router.route("open dashboard", input_mode="wakeword")

    assert result.intent == Intent.OPEN_TRADING_DASHBOARD
    validate.assert_called_once()
    execute.assert_called_once()


def test_common_natural_phrases_map_correctly(monkeypatch):
    _enable_instant(monkeypatch)
    from brain.intent_classifier import classify

    expected = {
        "can you open the dashboard": Intent.OPEN_TRADING_DASHBOARD,
        "bring up the dashboard": Intent.OPEN_TRADING_DASHBOARD,
        "what's on my screen": Intent.DESCRIBE_SCREEN,
        "look at this window": Intent.ANALYZE_ACTIVE_WINDOW,
        "what was I working on": Intent.WHAT_WERE_WE_DOING,
        "check why this failed": Intent.EXPLAIN_THIS_ERROR,
        "tell me what went wrong": Intent.EXPLAIN_THIS_ERROR,
        "continue from yesterday": Intent.WHAT_WERE_WE_DOING,
        "open the thing we were working on": Intent.WHAT_WERE_WE_DOING,
    }
    for phrase, intent in expected.items():
        req = classify(phrase)
        assert req.intent == intent, phrase
        assert req.confidence >= 0.85


def test_instant_mode_suppresses_spoken_fast_ack(monkeypatch, tmp_path):
    _enable_instant(monkeypatch)
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", tmp_path / "history.jsonl", raising=False)
    from brain.router import CommandRouter

    router = CommandRouter(session=SessionState())
    with (
        patch("conversation.latency_hints.deliver_fast_ack") as deliver,
        patch("brain.router.validate_intent", return_value=None),
        patch.object(
            router.registry,
            "execute",
            return_value=result_success(Intent.SHOW_JARVIS_STATUS, "JARVIS is running."),
        ),
        patch.object(router, "_finalize"),
    ):
        router.route("show jarvis status", input_mode="wakeword")

    deliver.assert_called_once()
    assert deliver.call_args.kwargs["speak"] is False


def test_latency_budget_metrics_exist():
    from actions.latency_actions import ShowLatencyStatusAction
    from voice.latency_tracker import (
        begin_voice_command,
        finish_and_log,
        mark_endpoint,
        mark_first_partial,
        mark_first_response,
        reset_latency_tracker,
        set_final_transcript_ms,
        set_route_timing,
    )

    reset_latency_tracker()
    begin_voice_command(source="wakeword")
    mark_first_partial(180.0)
    mark_endpoint(420.0)
    set_final_transcript_ms(210.0)
    set_route_timing(classify_ms=12.0, execute_ms=40.0, intent="show_jarvis_status")
    mark_first_response(480.0)
    finish_and_log()

    result = ShowLatencyStatusAction().execute(
        CommandRequest(
            raw_text="show voice latency budget",
            intent=Intent.SHOW_LATENCY_STATUS,
            confidence=1.0,
            params={"budget": "voice"},
        )
    )
    assert "wake_detect_ms" in result.summary
    assert "first_partial_ms" in result.summary
    assert "endpoint_ms" in result.summary
    assert "final_transcript_ms" in result.summary
    assert "classify_ms" in result.summary
    assert "first_response_ms" in result.summary
    assert "total_after_speech_end_ms" in result.summary
    assert "Targets" in result.summary


def test_show_voice_latency_budget_classifies(monkeypatch):
    _enable_instant(monkeypatch)
    from brain.intent_classifier import classify

    req = classify("show voice latency budget")
    assert req.intent == Intent.SHOW_LATENCY_STATUS
    assert req.params.get("budget") == "voice"

