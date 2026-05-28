"""Phase 59.2 — conversational TTS must not be blocked by tool-first mode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from conversation.human_runtime import (
    activate_session_for_tests,
    enable_human_conversational_runtime,
    reset_human_runtime_for_tests,
)
import config as cfg
from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, CommandResult, CommandRequest, Intent
from core.runtime_state import get_runtime_state
from voice.audio_status import reset_audio_status
from voice.human_interruption import on_user_speech_during_tts, reset_human_interruption_for_tests
from voice.tool_first_mode import TOOL_MODE_NOTICE, can_attempt_tts
from voice.tts_output_policy import (
    evaluate_tts_output,
    format_tts_output_diagnostics,
    reset_tts_output_policy_for_tests,
)
from ui.overlay_voice_status import get_last_overlay_voice_status, reset_overlay_voice_status_for_tests


def _setup_tool_first(monkeypatch) -> None:
    reset_audio_status()
    reset_human_runtime_for_tests()
    reset_tts_output_policy_for_tests()
    reset_overlay_voice_status_for_tests()
    reset_human_interruption_for_tests()
    get_runtime_state().speak_enabled = True
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)
    monkeypatch.setattr("config.HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)
    enable_human_conversational_runtime()


def test_tool_first_still_blocks_without_active_session(monkeypatch):
    _setup_tool_first(monkeypatch)

    with patch("voice.backend_verification.is_backend_initialized", return_value=False), patch(
        "voice.backend_verification.is_local_tts_synthesis_available",
        return_value=False,
    ):
        decision = evaluate_tts_output(speak_enabled=True, voice_path="test")
        assert decision.allowed is False
        assert decision.reason == "tool_first_unverified_backend"
        assert decision.overlay_status == "TTS BLOCKED"
        assert can_attempt_tts() is False


def test_conversational_session_bypasses_tool_first(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()

    decision = evaluate_tts_output(speak_enabled=True, voice_path="test")
    assert decision.allowed is True
    assert decision.reason == "conversational_session_priority"
    assert decision.session_active is True
    assert can_attempt_tts() is True


def test_mute_blocks_conversational_session(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()

    decision = evaluate_tts_output(speak_enabled=False, voice_path="test")
    assert decision.allowed is False
    assert decision.overlay_status == "MUTED"


def test_maybe_speak_result_allows_during_session(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()
    runtime = RuntimeState(speak_enabled=True, overlay_enabled=False)
    app = JarvisApp(runtime=runtime)
    result = CommandResult(
        intent=Intent.UNKNOWN,
        status=ActionStatus.SUCCESS,
        summary="Hello from the session.",
    )

    with patch(
        "conversation.human_runtime.speak_result_conversationally",
        return_value="mock_provider",
    ) as speak_conv:
        app._maybe_speak_result(result)

    speak_conv.assert_called_once_with(result)


def test_overlay_no_tool_mode_notice_during_session(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()
    runtime = RuntimeState(overlay_enabled=True, speak_enabled=True)
    app = JarvisApp(runtime=runtime)

    with patch("ui.overlay_app.notify_overlay_result") as hud:
        app._notify_overlay_result(
            CommandResult(
                intent=Intent.UNKNOWN,
                status=ActionStatus.SUCCESS,
                summary="Session reply.",
            )
        )

    hud.assert_called_once()
    assert TOOL_MODE_NOTICE not in hud.call_args.args[0]
    assert hud.call_args.kwargs["speaking"] is True


def test_overlay_shows_tool_mode_notice_without_session(monkeypatch):
    reset_human_runtime_for_tests()
    monkeypatch.setattr(cfg, "TOOL_FIRST_MODE", True, raising=False)
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False, raising=False)
    runtime = RuntimeState(overlay_enabled=True, speak_enabled=True)
    app = JarvisApp(runtime=runtime, skip_bootstrap=True)

    with patch("voice.backend_verification.is_backend_initialized", return_value=False), patch(
        "voice.backend_verification.is_local_tts_synthesis_available",
        return_value=False,
    ), patch("voice.backend_verification.is_conversational_runtime_enabled", return_value=False), patch(
        "voice.audio_status.is_debug_force_audio_enabled",
        return_value=False,
    ), patch("ui.overlay_app.notify_overlay_result") as hud:
        app._notify_overlay_result(
            CommandResult(
                intent=Intent.TOOL_MODE_STATUS,
                status=ActionStatus.SUCCESS,
                summary="Tool mode status.",
            )
        )

    assert TOOL_MODE_NOTICE in hud.call_args.args[0]
    assert hud.call_args.kwargs["speaking"] is False


def test_interruption_sets_overlay_status(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()

    on_user_speech_during_tts(partial_text="wait")

    assert get_last_overlay_voice_status() == "INTERRUPTED"


def test_tts_diagnostics_include_last_decision(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()
    evaluate_tts_output(speak_enabled=True, voice_path="diagnostics_test")

    text = format_tts_output_diagnostics()
    assert "conversational_session_priority" in text
    assert "session_active: yes" in text


def test_may_use_verified_speech_bypass_during_session(monkeypatch):
    _setup_tool_first(monkeypatch)
    activate_session_for_tests()

    from voice.audio_verified import may_use_verified_speech

    assert may_use_verified_speech() is True
