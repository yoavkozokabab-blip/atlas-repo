"""Smoke test for Phase 59 human conversational runtime."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as cfg
from actions.registry import ActionRegistry
from brain.operational_command_phrases import match_operational_priority_commands
from core.intent_validation import run_startup_intent_validation, validate_phase59_runtime_wiring
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, Intent
from conversation.conversation_metrics import reset_conversation_metrics_for_tests
from conversation.emotional_speech import infer_speech_style
from conversation.human_runtime import enable_human_conversational_runtime, reset_human_runtime_for_tests
from conversation.memory_runtime import reset_memory_runtime_for_tests
from voice.human_interruption import reset_human_interruption_for_tests


def _run_action(registry: ActionRegistry, phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, (phrase, getattr(gate, "summary", gate))
    result = registry.execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.status, result.summary)
    print(f"OK action {phrase!r}")
    return result.summary


def main() -> None:
    cfg.TTS_SAFE_MODE = False
    cfg.VOICE_RUNTIME_STABLE = False
    cfg.REALTIME_TTS_ENABLED = True
    cfg.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = True
    cfg.CONVERSATION_CONTINUOUS_MIC_ENABLED = True
    enable_human_conversational_runtime()

    issues = validate_phase59_runtime_wiring()
    assert not issues, issues
    run_startup_intent_validation(strict=True)
    print("OK phase59 wiring")

    style = infer_speech_style(text="Warning: trading mismatch detected urgently", intent="investigate")
    assert style.label in {"urgent", "warning", "investigation_critical", "investigation_moderate"}
    print("OK emotional speech style inference")

    with patch("integrations.ollama_client.OllamaClient") as mock_client:
        mock_client.return_value.stream_chat_tokens.return_value = iter(
            ["Hello. ", "This is a streaming response."]
        )
        from conversation.llm_streaming import stream_sentence_fragments

        chunks = list(stream_sentence_fragments("test question"))
        assert chunks, chunks
    print("OK llm sentence fragment streaming")

    with patch("voice.streaming_pipeline.StreamingPipeline.speak_response_stream", return_value="mock"):
        from conversation.llm_streaming import speak_streaming_response

        provider = speak_streaming_response("hello there", intent="conversational")
        assert provider
    print("OK preemptive conversational speak path")

    from voice.human_interruption import on_user_speech_during_tts

    with patch("voice.streaming_player.pause_playback_immediately"), patch(
        "voice.interruption_manager.on_user_speech_detected",
        return_value=type("R", (), {"stopped_tts": True, "preserved_response": True, "state": "user_barge_in"})(),
    ):
        assert on_user_speech_during_tts(partial_text="wait")
    print("OK human interruption model")

    registry = ActionRegistry()
    for phrase, intent in (
        ("show conversation runtime", Intent.SHOW_CONVERSATION_RUNTIME),
        ("show interruption metrics", Intent.SHOW_INTERRUPTION_METRICS),
        ("show conversational memory", Intent.SHOW_CONVERSATIONAL_MEMORY),
        ("benchmark full duplex conversation", Intent.BENCHMARK_FULL_DUPLEX_CONVERSATION),
        ("phase 59 status", Intent.PHASE59_STATUS),
    ):
        op = match_operational_priority_commands(phrase)
        assert op is not None and op.intent == intent, (phrase, op)
        _run_action(registry, phrase, intent)

    reset_conversation_metrics_for_tests()
    reset_human_runtime_for_tests()
    reset_memory_runtime_for_tests()
    reset_human_interruption_for_tests()
    print("SMOKE PASS phase59")


if __name__ == "__main__":
    main()
