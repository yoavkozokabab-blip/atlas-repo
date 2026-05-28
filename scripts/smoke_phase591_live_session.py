"""Live session smoke for Phase 59.1 — wakeword → active human conversation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as cfg
from conversation.conversation_metrics import get_last_conversation_metrics, reset_conversation_metrics_for_tests
from conversation.human_runtime import (
    enable_human_conversational_runtime,
    get_session_snapshot,
    is_session_active,
    reset_human_runtime_for_tests,
    run_human_conversation_session,
    should_start_human_session_after_wake,
)
from conversation.memory_runtime import load_memory_runtime, reset_memory_runtime_for_tests
from core.types import ActionStatus, CommandResult, CommandRequest, Intent
from voice.continuous_mic import reset_continuous_mic_for_tests
from voice.human_interruption import on_user_speech_during_tts, reset_human_interruption_for_tests
from voice.streaming_stt.session_policy import reset_streaming_session
from voice.streaming_stt.stream_session import StreamingSttResult


class _FakeApp:
    session = None

    def handle_text_command(self, raw_text, *, input_mode="wakeword", transcribed_text=None, print_result=False):
        del input_mode, transcribed_text, print_result
        return CommandResult(
            intent=Intent.UNKNOWN,
            status=ActionStatus.SUCCESS,
            summary=f"Handled {raw_text[:40]}",
        )


def _turn(text: str, *, partials: int = 2) -> StreamingSttResult:
    return StreamingSttResult(
        text=text,
        partial_updates=partials,
        decode_ms=12.0,
        record_seconds=1.5,
        endpoint_silence_ms=450.0,
    )


def _setup_cfg() -> None:
    cfg.TTS_SAFE_MODE = False
    cfg.VOICE_RUNTIME_STABLE = False
    cfg.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = True
    cfg.CONVERSATION_CONTINUOUS_MIC_ENABLED = True
    cfg.CONVERSATION_SESSION_IDLE_SECONDS = 2.0
    cfg.STT_STREAMING_BUFFER_ENABLED = True
    reset_streaming_session()
    enable_human_conversational_runtime()


def main() -> None:
    _setup_cfg()
    app = _FakeApp()
    assert should_start_human_session_after_wake(app)
    print("OK should_start_human_session_after_wake")

    turn_queue = [_turn("what is the weather today"), _turn("stop listening", partials=1)]

    def _mock_capture(*, on_partial=None, **kwargs):
        del kwargs
        item = turn_queue.pop(0) if turn_queue else _turn("")
        if on_partial and item.partial_updates:
            for i in range(item.partial_updates):
                on_partial(f"partial {i + 1}")
        return item

    def _mock_speak(chunks, **kwargs):
        del kwargs
        list(chunks)
        return "mock_provider"

    with patch("voice.continuous_mic.capture_turn", side_effect=_mock_capture), patch(
        "brain.intent_classifier.classify_rules",
        return_value=CommandRequest(raw_text="test", intent=Intent.UNKNOWN, confidence=0.4),
    ), patch(
        "integrations.ollama_client.OllamaClient.stream_chat_tokens",
        return_value=iter(["Sure. ", "I can help with that."]),
    ), patch(
        "voice.streaming_pipeline.StreamingPipeline.speak_response_stream",
        side_effect=_mock_speak,
    ):
        result = run_human_conversation_session(app=app)
        snap = get_session_snapshot()
        assert not is_session_active(), snap
        assert int(result.get("turns", 0)) >= 1, result
        assert int(result.get("partials", 0)) >= 1, result
        assert int(result.get("responses", 0)) >= 1, result
        metrics = get_last_conversation_metrics()
        assert metrics is not None
        assert metrics.first_partial_stt_ms is not None
        from conversation.conversation_metrics import get_conversation_metrics_history

        hist = get_conversation_metrics_history()
        assert any(h.llm_first_token_ms is not None for h in hist) or metrics.llm_first_token_ms is not None
    print("OK active human conversation session with partials and responses")

    with patch("voice.streaming_player.pause_playback_immediately"), patch(
        "voice.interruption_manager.on_user_speech_detected",
        return_value=type(
            "R",
            (),
            {"stopped_tts": True, "preserved_response": True, "state": "user_barge_in"},
        )(),
    ):
        assert on_user_speech_during_tts(partial_text="wait")
    print("OK interrupt during speech")

    _setup_cfg()
    turn_queue = [_turn("hello jarvis"), _turn("stop listening", partials=1)]

    def _mock_capture2(*, on_partial=None, **kwargs):
        del kwargs
        item = turn_queue.pop(0) if turn_queue else _turn("")
        if on_partial:
            on_partial("partial")
        return item

    def _mock_speak2(chunks, **kwargs):
        del kwargs
        list(chunks)
        return "mock"

    with patch("voice.continuous_mic.capture_turn", side_effect=_mock_capture2), patch(
        "brain.intent_classifier.classify_rules",
        return_value=CommandRequest(raw_text="test", intent=Intent.UNKNOWN, confidence=0.4),
    ), patch(
        "integrations.ollama_client.OllamaClient.stream_chat_tokens",
        return_value=iter(["Hello."]),
    ), patch(
        "voice.streaming_pipeline.StreamingPipeline.speak_response_stream",
        side_effect=_mock_speak2,
    ):
        run_human_conversation_session(app=app)
        mem = load_memory_runtime()
        assert int(mem.get("turn_count") or 0) >= 1
    print("OK multi-turn memory retention")

    with patch("conversation.human_runtime.should_start_human_session_after_wake", return_value=True), patch(
        "conversation.human_runtime.run_human_conversation_session",
        return_value={"turns": 1, "partials": 2, "responses": 1},
    ), patch("voice.latency_tracker.finish_and_log"), patch(
        "voice.wake_greeting.play_wake_greeting_async"
    ), patch("ui.overlay_app.notify_overlay_listening"), patch(
        "voice.wakeword_loop.begin_voice_command"
    ), patch("voice.wakeword_loop.mark_wake_detected"), patch(
        "voice.wakeword_loop.effective_wake_listen_seconds",
        return_value=45.0,
    ):
        from voice.wakeword_loop import run_post_wake_listening_session

        runtime = MagicMock()
        runtime.acquire_wake_listening_session.return_value = True
        app.runtime = runtime
        run_post_wake_listening_session(app, session_already_acquired=True)
    print("OK wakeword handoff to human session")

    reset_conversation_metrics_for_tests()
    reset_human_runtime_for_tests()
    reset_memory_runtime_for_tests()
    reset_continuous_mic_for_tests()
    reset_human_interruption_for_tests()
    print("SMOKE PASS phase591_live_session")


if __name__ == "__main__":
    main()
