"""Phase 44 tool-first mode tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from actions.voice_audio_actions import ToolModeStatusAction
from brain.intent_classifier import classify_rules
from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, CommandRequest, Intent
from voice.audio_status import reset_audio_status, set_selected_verified_audio_backend
from conversation.human_runtime import reset_human_runtime_for_tests
from voice.tool_first_mode import can_attempt_tts, format_tool_mode_status


def test_tool_mode_status_command_registered(monkeypatch):
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)

    assert classify_rules("tool mode status").intent == Intent.TOOL_MODE_STATUS
    result = ToolModeStatusAction().execute(
        CommandRequest(raw_text="tool mode status", intent=Intent.TOOL_MODE_STATUS)
    )

    assert result.status == ActionStatus.SUCCESS
    assert "TOOL_FIRST_MODE: yes" in result.summary
    assert "Elite Code + Trading Investigation Engine" in result.summary


def test_tool_first_degrades_tts_without_verified_backend(monkeypatch):
    reset_audio_status()
    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)

    assert can_attempt_tts() is False
    text = format_tool_mode_status()
    assert "TTS may run: no (deferred)" in text


def test_tool_first_allows_tts_after_verified_backend(monkeypatch):
    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)
    set_selected_verified_audio_backend("shell_subprocess_pyttsx3")

    assert can_attempt_tts() is True


def test_console_command_prints_text_and_skips_unverified_tts(monkeypatch):
    reset_audio_status()
    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)
    runtime = RuntimeState()
    runtime.speak_enabled = True
    runtime.overlay_enabled = False
    app = JarvisApp(runtime=runtime)
    printed: list[str] = []
    app.console = MagicMock()
    app.console.print.side_effect = lambda *a, **_k: printed.append(str(a[0]))

    with patch.object(app.tts, "speak") as speak:
        result = app.handle_text_command(
            "tool mode status",
            input_mode="console",
            print_result=False,
        )

    assert result.status == ActionStatus.SUCCESS
    assert printed
    speak.assert_not_called()


def test_tool_first_hud_result_not_speaking_without_verified(monkeypatch):
    reset_audio_status()
    reset_human_runtime_for_tests()
    monkeypatch.setattr("config.TOOL_FIRST_MODE", True, raising=False)
    runtime = RuntimeState()
    runtime.overlay_enabled = True
    runtime.speak_enabled = True
    app = JarvisApp(runtime=runtime)

    with patch("ui.overlay_app.notify_overlay_result") as hud:
        app.handle_text_command(
            "tool mode status",
            input_mode="console",
            print_result=False,
        )

    hud.assert_called_once()
    assert hud.call_args.kwargs["speaking"] is False
    assert "Audio output deferred" in hud.call_args.args[0]
