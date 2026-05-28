"""Smoke test for Phase 57 realtime streaming voice stack + voice safety guard."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from actions.phase57_actions import simulate_realtime_barge_in_for_tests
from actions.registry import ActionRegistry
from brain.intent_classifier import classify
from brain.router import CommandRouter
from core.intent_validation import run_startup_intent_validation, validate_phase57_runtime_wiring
from core.security import validate_intent
from core.types import ActionStatus, CommandRequest, CommandResult, Intent
from voice.backend_manager import health_check, primary_backend_name, speak_stream
from voice.engines.base import SynthesisChunk
from voice.providers.registry import speak_with_failover
from voice.realtime_tts import (
    cancel_active_speech,
    is_realtime_tts_enabled,
    reset_realtime_tts_for_tests,
    speak_realtime,
    speak_realtime_parallel,
    split_sentences,
)
from voice.streaming_player import reset_streaming_player
from voice.voice_command_guard import evaluate_voice_command, is_voice_command_guard_enabled


def _setup(tmp: Path) -> None:
    import config as cfg

    cfg.DATA_DIR = tmp / "data"
    cfg.TTS_SAFE_MODE = False
    cfg.VOICE_RUNTIME_STABLE = False
    cfg.VOICE_COMMAND_GUARD_ENABLED = True
    cfg.REALTIME_TTS_ENABLED = True
    cfg.PYTTSX3_FALLBACK_ONLY = True
    cfg.TTS_PRIMARY_BACKEND = "realtime"
    cfg.TTS_FALLBACK_BACKEND = "pyttsx3_direct"
    cfg.FORCE_AUDIO_SUCCESS_FOR_DEBUG = True
    from voice.audio_runtime_init import initialize_audio_runtime_at_startup

    initialize_audio_runtime_at_startup()


def _run_action(registry: ActionRegistry, phrase: str, intent: Intent) -> str:
    req = CommandRequest(raw_text=phrase, intent=intent)
    gate = validate_intent(req)
    assert gate is None, gate
    result = registry.execute(req)
    assert result.status == ActionStatus.SUCCESS, (phrase, result.summary)
    return result.summary


class _MockStreamProvider:
    name = "mock_stream"
    fallback_only = False

    def is_available(self):
        return True

    def health(self):
        from voice.providers.base import ProviderHealth

        return ProviderHealth(name=self.name, available=True, latency_class="low")

    def stream(self, text, *, voice="", rate_raw="", prosody=None):
        del voice, rate_raw, prosody
        yield SynthesisChunk(data=b"\x00" * 12000, mime="audio/mpeg", viseme_hint=0.7)

    def cancel(self):
        cancel_active_speech()

    def last_time_to_first_audio_ms(self):
        return 25.0


def _route_voice(router: CommandRouter, text: str) -> CommandResult:
    return router.route(text, input_mode="voice", transcribed_text=text)


def main() -> None:
    issues = run_startup_intent_validation(strict=False)
    assert not issues, [i.format() for i in issues]
    wiring = validate_phase57_runtime_wiring()
    assert not wiring, [i.format() for i in wiring]
    print("OK phase57 wiring")

    tmp = Path(tempfile.mkdtemp()) / "phase57"
    _setup(tmp)
    reset_realtime_tts_for_tests()
    reset_streaming_player()
    assert is_realtime_tts_enabled() is True
    assert is_voice_command_guard_enabled() is True
    assert primary_backend_name() == "realtime"
    print("OK realtime enabled + guard + primary backend")

    oh = classify("Oh")
    assert oh.intent != Intent.OPEN_WEBSITE, (oh.intent.value, oh.confidence)
    print("OK classifier no longer maps Oh -> open_website")

    chrome = classify("open Chrome")
    assert chrome.intent == Intent.OPEN_CHROME, chrome.intent.value
    chrome_guard = evaluate_voice_command(chrome, input_mode="voice")
    assert chrome_guard is None, chrome_guard
    print("OK open Chrome passes voice guard")

    oh_guard = evaluate_voice_command(oh, input_mode="voice")
    assert oh_guard is not None and oh_guard.blocked, oh_guard
    router = CommandRouter()
    oh_result = _route_voice(router, "Oh")
    assert oh_result.status in {ActionStatus.BLOCKED, ActionStatus.CLARIFICATION_NEEDED}, oh_result
    print("OK voice transcript Oh blocked")

    risky = classify("open youtube")
    risky_guard = evaluate_voice_command(risky, input_mode="voice")
    assert risky_guard is not None and risky_guard.requires_confirmation, risky_guard
    risky_result = _route_voice(router, "open youtube")
    assert risky_result.status == ActionStatus.CONFIRMATION_REQUIRED, risky_result.summary
    assert "Did you mean" in risky_result.summary
    print("OK risky voice command requires confirmation")

    assert split_sentences("Hello. Still here? Yes!") == ["Hello.", "Still here?", "Yes!"]
    print("OK sentence splitting")

    mock = _MockStreamProvider()

    def _mock_failover(text, **kwargs):
        del kwargs
        return mock.name, mock.stream(text), mock

    with patch(
        "voice.realtime_tts.speak_with_failover",
        side_effect=_mock_failover,
    ), patch(
        "voice.realtime_tts.stream_mp3_chunks_incremental",
        lambda *_args, **_kwargs: True,
    ), patch(
        "voice.interruption_manager.on_jarvis_speech_started",
        lambda *_a, **_k: None,
    ), patch(
        "voice.interruption_manager.on_jarvis_speech_finished",
        lambda *_a, **_k: None,
    ):
        provider = speak_realtime("First sentence. Second sentence.")
        assert provider == "mock_stream"
        print("OK speak_realtime sentence chunks")

        def _chunks():
            yield "Jarvis is "
            time.sleep(0.05)
            yield "still speaking."

        provider = speak_realtime_parallel(_chunks())
        assert provider == "mock_stream"
        print("OK parallel streaming")

        with patch("voice.backend_manager.speak_with_backend", return_value="mock_stream"):
            assert speak_stream("normal speech path probe") == "mock_stream"
        health = health_check()
        assert health["primary_backend"] == "realtime"
        print("OK backend speak_stream + health_check")

        simulate_realtime_barge_in_for_tests()
        print("OK interrupt simulation")

    registry = ActionRegistry()
    _run_action(registry, "show voice latency", Intent.SHOW_VOICE_LATENCY)
    status = _run_action(registry, "phase 57 status", Intent.PHASE57_STATUS)
    assert "Realtime TTS runtime" in status
    assert "Voice command safety guard" in status
    print("OK show voice latency + phase57 status")

    with patch(
        "actions.phase57_actions.speak_realtime",
        return_value="mock_stream",
    ), patch(
        "actions.phase57_actions.cancel_active_speech",
        return_value=True,
    ), patch(
        "actions.phase57_actions.on_user_speech_detected",
        lambda *_a, **_k: None,
        create=True,
    ):
        test = _run_action(registry, "test realtime voice", Intent.TEST_REALTIME_VOICE)
        assert "Realtime voice test OK" in test
        print("OK test realtime voice")

        interrupt = _run_action(registry, "test interrupt speech", Intent.TEST_INTERRUPT_SPEECH)
        assert "Interrupt speech test OK" in interrupt
        print("OK test interrupt speech")

    from voice.providers.registry import get_provider_chain, select_provider

    selected = select_provider()
    chain = get_provider_chain()
    non_fallback = [p.name for p in chain if not p.fallback_only]
    assert non_fallback, "expected streaming providers in chain"
    assert selected is None or not selected.fallback_only or all(
        not p.is_available() for p in chain if not p.fallback_only
    ), selected
    print("OK primary provider chain excludes pyttsx3 unless failover")

    from voice.providers.provider_health import show_realtime_provider_status

    assert "Realtime TTS provider status" in show_realtime_provider_status()
    print("OK show realtime provider status")

    with patch(
        "voice.providers.openai_realtime_tts.OpenAIRealtimeTtsProvider.is_available",
        return_value=False,
    ), patch(
        "voice.providers.elevenlabs_streaming.ElevenLabsStreamingProvider.is_available",
        return_value=False,
    ), patch(
        "voice.providers.piper_local.PiperLocalProvider.is_available",
        return_value=True,
    ), patch(
        "voice.providers.piper_local.PiperLocalProvider.stream",
        lambda self, text, **kwargs: iter([SynthesisChunk(data=b"x" * 8000, mime="audio/wav")]),
    ):
        name, _chunks, _provider = speak_with_failover("failover probe")
        assert name == "piper"
        print("OK provider failover selection")

    print("SMOKE PASS phase57")


if __name__ == "__main__":
    main()
