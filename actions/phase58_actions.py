"""Phase 58 ultra-low-latency realtime voice actions."""

from __future__ import annotations

import threading
import time

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from core.env_precedence import format_runtime_config_mismatches, format_runtime_config_sources
from voice.duplex_runtime import show_duplex_runtime_status
from voice.realtime_tts import cancel_active_speech, is_realtime_tts_enabled, speak_realtime
from voice.voice_latency_metrics import format_realtime_latency_breakdown, format_voice_latency_status


class _ReadOnlyPhase58Action(BaseAction):
    intent: str
    _fn = None

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        body = self._fn()
        return result_success(Intent(self.intent), body, data={"read_only": True})


class ShowRealtimeLatencyBreakdownAction(_ReadOnlyPhase58Action):
    intent = Intent.SHOW_REALTIME_LATENCY_BREAKDOWN.value
    _fn = staticmethod(format_realtime_latency_breakdown)


class ShowRuntimeConfigSourcesAction(_ReadOnlyPhase58Action):
    intent = Intent.SHOW_RUNTIME_CONFIG_SOURCES.value
    _fn = staticmethod(format_runtime_config_sources)


class ShowRuntimeConfigMismatchesAction(_ReadOnlyPhase58Action):
    intent = Intent.SHOW_RUNTIME_CONFIG_MISMATCHES.value
    _fn = staticmethod(format_runtime_config_mismatches)


class TestWebsocketRealtimeVoiceAction(BaseAction):
    intent = Intent.TEST_WEBSOCKET_REALTIME_VOICE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not is_realtime_tts_enabled():
            return result_failed(
                Intent.TEST_WEBSOCKET_REALTIME_VOICE,
                "Realtime TTS disabled.",
            )
        try:
            provider = speak_realtime(
                "Websocket realtime voice online.",
                preferred_provider="elevenlabs",
            )
            body = (
                f"Websocket realtime voice test OK.\n"
                f"  provider: {provider or 'unknown'}\n"
                f"{format_realtime_latency_breakdown()}\n"
                f"{show_duplex_runtime_status()}"
            )
            return result_success(Intent.TEST_WEBSOCKET_REALTIME_VOICE, body)
        except Exception as exc:
            return result_failed(
                Intent.TEST_WEBSOCKET_REALTIME_VOICE,
                f"Websocket realtime voice test failed: {exc}\n{format_realtime_latency_breakdown()}",
            )


class BenchmarkRealtimeStreamingAction(BaseAction):
    intent = Intent.BENCHMARK_REALTIME_STREAMING.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.providers.provider_health import benchmark_all_providers, format_benchmark_report

        results = benchmark_all_providers(probe_text="Streaming benchmark probe.")
        lines = [
            format_benchmark_report(results),
            "",
            "Streaming playback benchmark (mock path when providers unavailable):",
        ]
        if is_realtime_tts_enabled():
            try:
                worker = threading.Thread(
                    target=lambda: speak_realtime("Streaming benchmark playback sample."),
                    daemon=True,
                )
                worker.start()
                time.sleep(0.05)
                cancel_active_speech()
                worker.join(timeout=2.0)
                lines.append(format_realtime_latency_breakdown())
            except Exception as exc:
                lines.append(f"  playback benchmark skipped: {exc}")
        else:
            lines.append("  realtime TTS disabled")
        lines.append("")
        lines.append(format_voice_latency_status())
        return result_success(Intent.BENCHMARK_REALTIME_STREAMING, "\n".join(lines), data={"read_only": True})
