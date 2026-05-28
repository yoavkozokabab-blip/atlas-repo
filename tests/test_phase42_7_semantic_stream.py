"""Phase 42.7 — semantic streaming conversation engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from conversation.semantic_stream.action_planner import build_action_plan
from conversation.semantic_stream.confidence_tracker import record_confidence, reset_confidence_tracker
from conversation.semantic_stream.conversation_graph import get_conversation_graph, reset_conversation_graph
from conversation.semantic_stream.correction_handler import apply_realtime_correction
from conversation.semantic_stream.engine import on_partial_transcript, reset_conversation_stream
from conversation.semantic_stream.interruption_handler import handle_streaming_interruption
from conversation.semantic_stream.multi_intent import decompose_utterance
from conversation.semantic_stream.profiling import BudgetTimer
from conversation.semantic_stream.reformulation import reformulate_with_context
from conversation.semantic_stream.turn_taking import TurnPhase, get_turn_state, reset_turn_state


@pytest.fixture(autouse=True)
def _clean():
    reset_conversation_stream()
    yield
    reset_conversation_stream()


@pytest.fixture
def _enable_conv(monkeypatch):
    monkeypatch.setattr("config.CONVERSATION_SEMANTIC_STREAM_ENABLED", True, raising=False)
    monkeypatch.setattr("config.CONV_SEMANTIC_UPDATE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.CONV_SEMANTIC_LATENCY_BUDGET_MS", 500, raising=False)
    monkeypatch.setattr("config.CONV_ACTION_PLAN_ENABLED", True, raising=False)


def test_partial_semantic_updates_confidence(_enable_conv):
    reset_confidence_tracker()
    t1 = record_confidence(intent="run_diagnostics", confidence=0.6, partial_text="run diag")
    t2 = record_confidence(intent="run_diagnostics", confidence=0.82, partial_text="run diagnostics")
    assert t2.latest_confidence >= t1.latest_confidence
    assert t2.latest_intent == "run_diagnostics"


def test_correction_mid_sentence():
    r = apply_realtime_correction("actually open dashboard", previous_text="open dash")
    assert r.applied
    assert "dashboard" in r.stripped_text.lower()


def test_context_continuation_open_it():
    reset_conversation_graph()
    from conversation.semantic_stream.conversation_graph import record_intent_candidate

    record_intent_candidate("show_latest_live_report", confidence=0.9, source="test")
    text, reason = reformulate_with_context("open it")
    assert "report" in text.lower()
    assert reason


def test_multi_intent_decomposition():
    plan = decompose_utterance("open dashboard and then show system status")
    assert plan.combined
    assert len(plan.segments) >= 2


def test_action_plan_does_not_execute(_enable_conv):
    with patch("actions.registry.ActionRegistry.execute") as execute:
        with patch(
            "language.hybrid_understanding.classify_hybrid",
        ) as classify:
            from core.types import CommandRequest, Intent

            classify.return_value = (
                CommandRequest(
                    raw_text="run diagnostics",
                    intent=Intent.RUN_DIAGNOSTICS,
                    confidence=0.92,
                ),
                None,
            )
            plan = build_action_plan("run diagnostics")
            assert plan.actions
            execute.assert_not_called()


def test_interruption_turn_phase():
    reset_turn_state()
    turn = get_turn_state()
    turn.on_jarvis_speak_start()
    handle_streaming_interruption(speech_detected=True)
    assert get_turn_state().phase == TurnPhase.USER_INTERRUPT


def test_on_partial_transcript_no_execute(_enable_conv):
    with patch("actions.registry.ActionRegistry.execute") as execute:
        with patch("language.semantic_intent.understand_semantic") as sem:
            from language.semantic_intent import SemanticUnderstanding

            sem.return_value = SemanticUnderstanding(
                candidate_intent="show_failing_tests",
                confidence=0.88,
                canonical_command="show failing tests",
                source="semantic_pattern",
            )
            snap = on_partial_transcript("show me what failed", speech_detected=True)
            assert snap.primary_intent == "show_failing_tests"
            execute.assert_not_called()


def test_latency_budget_profile():
    with BudgetTimer() as timer:
        timer.mark_parse_done()
        timer.mark_plan_done()
        prof = timer.finish(partial_len=10, intent="x", confidence=0.5)
    assert prof.total_ms >= 0
    assert prof.budget_ms > 0


def test_overlapping_stt_tts_barge_in(_enable_conv, monkeypatch):
    monkeypatch.setattr("config.TTS_BARGE_IN_ENABLED", True, raising=False)
    reset_turn_state()
    get_turn_state().on_jarvis_speak_start()
    with patch("voice.speech_controller.barge_in_if_speaking", return_value=True) as barge:
        evt = handle_streaming_interruption(speech_detected=True)
        assert evt.detected
        barge.assert_called()


def test_conversation_graph_records_nodes(_enable_conv):
    with patch("language.semantic_intent.understand_semantic") as sem:
        from language.semantic_intent import SemanticUnderstanding

        sem.return_value = SemanticUnderstanding(
            candidate_intent="run_diagnostics",
            confidence=0.9,
            canonical_command="run diagnostics",
        )
        on_partial_transcript("run diagnostics", is_final=True)
    g = get_conversation_graph()
    assert any(n.kind == "utterance" for n in g.nodes)
    assert any(n.kind == "intent" for n in g.nodes)


def test_streaming_integration_with_semantic(monkeypatch):
    monkeypatch.setattr("config.STT_STREAMING_BUFFER_ENABLED", True, raising=False)
    monkeypatch.setattr("config.CONVERSATION_SEMANTIC_STREAM_ENABLED", True, raising=False)
    monkeypatch.setattr("config.STT_PARTIAL_INTERVAL_MS", 50, raising=False)
    monkeypatch.setattr("config.STT_STREAM_ENDPOINT_SILENCE_MS", 200, raising=False)
    monkeypatch.setattr("config.STT_INCREMENTAL_DECODE_MIN_MS", 0, raising=False)
    monkeypatch.setattr("config.CONV_SEMANTIC_UPDATE_MIN_MS", 0, raising=False)

    calls = {"n": 0}

    def _transcribe(_a, _s):
        calls["n"] += 1
        return "open dashboard" if calls["n"] > 1 else "open"

    import numpy as np

    tone = (0.2 * np.sin(np.linspace(0, 4, 6400))).astype(np.float32)
    chunks = [tone] * 10 + [np.zeros(1280, dtype=np.float32)] * 10
    idx = {"i": 0}

    def _feed():
        i = min(idx["i"], len(chunks) - 1)
        idx["i"] = i + 1
        return chunks[i]

    from voice.streaming_stt.stream_session import StreamingSttSession

    with patch("language.semantic_intent.understand_semantic") as sem:
        from language.semantic_intent import SemanticUnderstanding

        sem.return_value = SemanticUnderstanding(
            candidate_intent="open_trading_dashboard",
            confidence=0.9,
            canonical_command="open dashboard",
        )
        with patch(
            "voice.streaming_stt.transcribe.transcribe_stream_final",
            side_effect=lambda _audio, _sr, partial_text="": partial_text,
        ):
            out = StreamingSttSession(
                transcribe_fn=_transcribe,
                audio_feed=_feed,
            ).run_until_endpoint(max_seconds=2.5)
    assert out.partial_updates >= 1


def test_phase427_config_keys_loaded():
    import config as cfg

    assert hasattr(cfg, "STT_STREAM_MAX_BUFFER_SECONDS")
    assert hasattr(cfg, "STT_STREAM_CHUNK_MS")
    assert hasattr(cfg, "STT_STREAM_OVERLAP_MS")
    assert hasattr(cfg, "CONV_CONTEXT_CARRY_ENABLED")
    assert hasattr(cfg, "CONV_INTERRUPTION_ENABLED")
    assert hasattr(cfg, "CONV_REFORMULATION_ENABLED")
    assert hasattr(cfg, "CONV_CONFIDENCE_STABILITY_THRESHOLD")
    assert cfg.streaming_chunk_samples() >= 320


def test_confidence_stability_uses_threshold(monkeypatch):
    monkeypatch.setattr("config.CONV_CONFIDENCE_STABILITY_THRESHOLD", 0.72, raising=False)
    reset_confidence_tracker()
    record_confidence(intent="x", confidence=0.8, partial_text="a")
    t = record_confidence(intent="x", confidence=0.85, partial_text="ab")
    assert t.stable is True
    reset_confidence_tracker()
    record_confidence(intent="x", confidence=0.5, partial_text="a")
    t2 = record_confidence(intent="x", confidence=0.85, partial_text="ab")
    assert t2.stable is False
