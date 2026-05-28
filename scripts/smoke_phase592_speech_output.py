"""Phase 59.2 smoke — conversational session TTS not blocked by tool-first mode."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as cfg
from conversation.human_runtime import (
    activate_session_for_tests,
    enable_human_conversational_runtime,
    reset_human_runtime_for_tests,
)
from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, CommandResult, Intent
from core.runtime_state import get_runtime_state
from voice.audio_status import reset_audio_status
from voice.tts_output_policy import evaluate_tts_output, reset_tts_output_policy_for_tests
from ui.overlay_voice_status import reset_overlay_voice_status_for_tests


def main() -> None:
    reset_audio_status()
    reset_human_runtime_for_tests()
    reset_tts_output_policy_for_tests()
    reset_overlay_voice_status_for_tests()
    get_runtime_state().speak_enabled = True

    cfg.TOOL_FIRST_MODE = True
    cfg.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = True
    cfg.TTS_SAFE_MODE = False
    cfg.VOICE_RUNTIME_STABLE = False
    enable_human_conversational_runtime()
    activate_session_for_tests()

    decision = evaluate_tts_output(speak_enabled=True, voice_path="smoke592")
    assert decision.allowed, decision
    assert decision.reason == "conversational_session_priority"
    print("OK policy allows conversational TTS under tool-first mode")

    runtime = RuntimeState(speak_enabled=True, overlay_enabled=False)
    app = JarvisApp(runtime=runtime)
    result = CommandResult(
        intent=Intent.UNKNOWN,
        status=ActionStatus.SUCCESS,
        summary="Live verification reply.",
    )

    spoken: list[str] = []

    def _mock_speak_conv(res):
        spoken.append(res.summary or "")
        return "mock_provider"

    with patch(
        "conversation.human_runtime.speak_result_conversationally",
        side_effect=_mock_speak_conv,
    ):
        app._maybe_speak_result(result)

    assert spoken, "expected conversational speak path during active session"
    print("OK maybe_speak_result invoked conversational TTS")

    with patch(
        "voice.realtime_tts.speak_realtime",
        return_value="mock_realtime",
    ) as speak_rt:
        from voice.realtime_tts import speak_realtime as _entry

        _ = _entry("Verification phrase.")

    speak_rt.assert_called_once()
    print("OK speak_realtime reached during session")

    print("SMOKE PASS phase592_speech_output")


if __name__ == "__main__":
    main()
