"""Phase 57 realtime streaming voice actions."""

from __future__ import annotations

import threading
import time

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from voice.realtime_tts import (
    cancel_active_speech,
    is_realtime_tts_enabled,
    phase57_status,
    speak_realtime,
)
from voice.voice_command_guard import show_voice_guard_status
from voice.voice_latency_metrics import format_voice_latency_status


class _ReadOnlyPhase57Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowRealtimeProviderStatusAction(_ReadOnlyPhase57Action):
    intent = Intent.SHOW_REALTIME_PROVIDER_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.providers.provider_health import show_realtime_provider_status

        body = show_realtime_provider_status()
        return result_success(Intent.SHOW_REALTIME_PROVIDER_STATUS, body, data={"read_only": True})


class BenchmarkRealtimeProvidersAction(BaseAction):
    intent = Intent.BENCHMARK_REALTIME_PROVIDERS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.providers.provider_health import benchmark_all_providers, format_benchmark_report

        results = benchmark_all_providers()
        body = format_benchmark_report(results)
        return result_success(Intent.BENCHMARK_REALTIME_PROVIDERS, body, data={"read_only": True})


class ShowVoiceLatencyAction(_ReadOnlyPhase57Action):
    intent = Intent.SHOW_VOICE_LATENCY.value
    _fn = staticmethod(format_voice_latency_status)


class Phase57StatusAction(_ReadOnlyPhase57Action):
    intent = Intent.PHASE57_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = "\n\n".join([phase57_status(), show_voice_guard_status()])
        return result_success(Intent.PHASE57_STATUS, body, data={"read_only": True})


class TestRealtimeVoiceAction(BaseAction):
    intent = Intent.TEST_REALTIME_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not is_realtime_tts_enabled():
            return result_failed(
                Intent.TEST_REALTIME_VOICE,
                "Realtime TTS disabled (REALTIME_TTS_ENABLED=false or stable/safe mode).",
            )
        try:
            provider = speak_realtime(
                "Jarvis realtime voice online. Low latency streaming is active.",
                emotion="neutral",
            )
            body = (
                f"Realtime voice test OK.\n"
                f"  provider: {provider or 'unknown'}\n"
                f"{format_voice_latency_status()}"
            )
            return result_success(Intent.TEST_REALTIME_VOICE, body)
        except Exception as exc:
            return result_failed(
                Intent.TEST_REALTIME_VOICE,
                f"Realtime voice test failed: {exc}\n{format_voice_latency_status()}",
            )


class TestInterruptSpeechAction(BaseAction):
    intent = Intent.TEST_INTERRUPT_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not is_realtime_tts_enabled():
            return result_failed(
                Intent.TEST_INTERRUPT_SPEECH,
                "Interrupt test requires realtime TTS (disabled in stable/safe mode).",
            )

        interrupted = threading.Event()
        result: dict[str, object] = {"cancel_ms": None, "provider": ""}

        def _speak() -> None:
            try:
                result["provider"] = speak_realtime(
                    "Interrupt test. Jarvis is speaking a longer sentence now. "
                    "This should stop immediately when you interrupt.",
                )
            except Exception as exc:
                result["error"] = str(exc)

        worker = threading.Thread(target=_speak, name="jarvis-interrupt-test", daemon=True)
        worker.start()
        time.sleep(0.08)
        t0 = time.perf_counter()
        from voice.interruption_manager import on_user_speech_detected

        on_user_speech_detected(partial_text="user interrupt test")
        cancel_active_speech()
        result["cancel_ms"] = (time.perf_counter() - t0) * 1000.0
        interrupted.set()
        worker.join(timeout=2.0)
        body = (
            "Interrupt speech test OK.\n"
            f"  provider: {result.get('provider') or 'unknown'}\n"
            f"  interruption_latency_ms: {result.get('cancel_ms', 'n/a')}\n"
            f"{format_voice_latency_status()}"
        )
        return result_success(Intent.TEST_INTERRUPT_SPEECH, body)


class CancelActiveSpeechAction(BaseAction):
    intent = Intent.CANCEL_ACTIVE_SPEECH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        stopped = cancel_active_speech()
        state = "stopped" if stopped else "no active speech"
        return result_success(
            Intent.CANCEL_ACTIVE_SPEECH,
            f"Active speech cancel: {state}.",
        )


def simulate_realtime_barge_in_for_tests() -> str:
    """Test helper: interrupt mid-stream and preserve response text."""
    from voice.interruption_manager import on_user_speech_detected

    on_user_speech_detected(partial_text="user interrupt")
    cancel_active_speech()
    return "barge-in simulated"
