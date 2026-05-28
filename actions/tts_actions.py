"""TTS status (read-only diagnostics)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_failed, result_success
from core.runtime_bootstrap import format_show_tts_debug
from core.types import CommandRequest, CommandResult, Intent
from voice.tts_status import format_tts_status, get_tts_status


class ShowTtsStatusAction(BaseAction):
    intent = Intent.SHOW_TTS_STATUS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        status = get_tts_status()
        return result_success(
            Intent.SHOW_TTS_STATUS,
            format_tts_status(status),
            data={
                "read_only": True,
                "engine": status.engine,
                "voice": status.voice,
                "rate_raw": status.rate_raw,
                "async": status.async_mode,
                "edge_available": status.edge_available,
                "pyttsx_available": status.pyttsx_available,
                "last_provider": status.last_provider,
            },
        )


class ShowTtsDebugAction(BaseAction):
    intent = Intent.SHOW_TTS_DEBUG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        return result_success(
            Intent.SHOW_TTS_DEBUG,
            format_show_tts_debug(),
            data={"read_only": True},
        )


class TestTtsPlaybackAction(BaseAction):
    intent = Intent.TEST_TTS_PLAYBACK.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.backend_verification import format_tts_playback_self_test_report, run_tts_playback_self_test

        result = run_tts_playback_self_test()
        body = format_tts_playback_self_test_report(result)
        if result.success:
            return result_success(Intent.TEST_TTS_PLAYBACK, body, data={"read_only": True})
        return result_failed(Intent.TEST_TTS_PLAYBACK, body)


class TestDirectTtsAction(BaseAction):
    intent = Intent.TEST_DIRECT_TTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from voice.playback_metrics import format_playback_metrics
        from voice.pyttsx3_completion import run_direct_tts_isolated_test

        result = run_direct_tts_isolated_test()
        body = (
            "Direct TTS isolated test:\n"
            f"  success: {'yes' if result.ok else 'no'}\n"
            f"  elapsed ms: {result.elapsed_ms:.1f}\n"
            f"  fallback: {result.fallback_path or 'none'}\n"
            f"  utterance started: {'yes' if result.utterance_started else 'no'}\n"
            f"  utterance finished: {'yes' if result.utterance_finished else 'no'}\n"
            f"  error: {result.error or 'none'}\n"
            f"\n{format_playback_metrics()}"
        )
        if result.ok:
            return result_success(
                Intent.TEST_DIRECT_TTS,
                body,
                data={"read_only": True, "skip_speak": True, "already_spoken": True},
            )
        return result_failed(Intent.TEST_DIRECT_TTS, body)
