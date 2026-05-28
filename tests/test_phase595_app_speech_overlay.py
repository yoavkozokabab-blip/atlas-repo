"""Phase 59.5 — app speech path, diagnostic compact TTS, overlay shutdown safety."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.types import ActionStatus, CommandResult, Intent


def _result(intent: Intent, summary: str, **data: object) -> CommandResult:
    return CommandResult(
        intent=intent,
        status=ActionStatus.SUCCESS,
        summary=summary,
        data=dict(data),
    )


def test_compact_tts_debug_summary_is_short() -> None:
    from voice.diagnostic_speech import compact_spoken_summary_for_result

    long_body = (
        "TTS debug:\n"
        "  speak_enabled: yes\n"
        "  muted: no\n"
        "  audio_mode: conversational\n"
        "  backend: unverified\n"
        "  verified backend: none\n"
        "  backend initialized: yes\n"
        "  last suppression reason: conversational_runtime_local_fallback\n"
        "  session active: no\n"
        "  tool_first_mode: yes\n"
        "  conversational runtime enabled: yes\n"
        "  continuous mic: yes\n"
        "  bootstrap applied: yes\n"
        "\n"
        "TTS output diagnostics (Phase 59.2):\n"
        "  allowed: yes\n"
        "  reason: conversational_runtime_local_fallback\n"
        "\n"
        "Direct playback metrics (Phase 59.5):\n"
        "  audio started: yes\n"
        "  playback completed: yes\n"
        "  playback timeout: no\n"
    )
    result = _result(Intent.SHOW_TTS_DEBUG, long_body, read_only=True)
    spoken = compact_spoken_summary_for_result(result)
    assert spoken
    assert len(spoken) < 220
    assert "TTS debug" in spoken
    assert "conversational" in spoken.lower()
    assert "speak_enabled: yes" not in spoken


def test_test_direct_tts_skips_second_speak() -> None:
    from voice.diagnostic_speech import should_skip_result_speech

    result = _result(
        Intent.TEST_DIRECT_TTS,
        "Direct TTS isolated test:\n  success: yes",
        read_only=True,
        skip_speak=True,
        already_spoken=True,
    )
    assert should_skip_result_speech(result) is True


def test_maybe_speak_command_uses_direct_path_without_active_session() -> None:
    from core.app import JarvisApp

    app = JarvisApp(skip_bootstrap=True)
    app.speak_enabled = True
    result = _result(Intent.UNKNOWN, "Short command reply for the user.")

    with patch(
        "conversation.human_runtime.is_human_conversational_runtime_enabled",
        return_value=True,
    ), patch("conversation.human_runtime.is_session_active", return_value=False), patch(
        "conversation.human_runtime.speak_result_conversationally",
    ) as conv_speak, patch(
        "voice.tts_output_policy.evaluate_tts_output",
    ) as eval_mock, patch(
        "voice.diagnostic_speech.speak_compact_diagnostic",
        return_value=True,
    ) as direct_speak:
        decision = MagicMock(allowed=True, reason="allowed", overlay_status="SPEAKING")
        eval_mock.return_value = decision
        app._maybe_speak_result(result)

    conv_speak.assert_not_called()
    direct_speak.assert_called_once()
    assert "Short command reply" in direct_speak.call_args[0][0]


def test_maybe_speak_diagnostic_uses_compact_not_full_summary() -> None:
    from core.app import JarvisApp

    app = JarvisApp(skip_bootstrap=True)
    app.speak_enabled = True
    long_body = "TTS debug:\n" + "\n".join(f"  line_{i}: value_{i}" for i in range(40))
    result = _result(Intent.SHOW_TTS_DEBUG, long_body, read_only=True)

    with patch(
        "voice.tts_output_policy.evaluate_tts_output",
    ) as eval_mock, patch(
        "voice.diagnostic_speech.speak_compact_diagnostic",
        return_value=True,
    ) as direct_speak, patch(
        "conversation.human_runtime.speak_result_conversationally",
    ) as conv_speak:
        decision = MagicMock(allowed=True, reason="allowed", overlay_status="SPEAKING")
        eval_mock.return_value = decision
        app._maybe_speak_result(result)

    conv_speak.assert_not_called()
    direct_speak.assert_called_once()
    spoken = direct_speak.call_args[0][0]
    assert len(spoken) < 300
    assert "line_39" not in spoken


def test_overlay_shutdown_idempotent() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ui.overlay_app import JarvisOverlayWindow
    from ui.overlay_state import OverlayState

    app = QApplication.instance() or QApplication([])
    state = OverlayState()
    window = JarvisOverlayWindow(state, opacity=0.9, always_on_top=False, theme_name="classic")
    window.shutdown()
    window.shutdown()
    assert getattr(window, "_closed", False) is True
    del window
    app.processEvents()


def test_show_tts_debug_action_is_read_only() -> None:
    from actions.tts_actions import ShowTtsDebugAction
    from core.types import CommandRequest

    with patch("core.runtime_bootstrap.format_show_tts_debug", return_value="TTS debug:\n  speak_enabled: yes"):
        dbg = ShowTtsDebugAction().execute(
            CommandRequest(raw_text="show tts debug", intent=Intent.SHOW_TTS_DEBUG)
        )
    assert dbg.status == ActionStatus.SUCCESS
    assert dbg.data.get("read_only") is True


def test_test_direct_tts_action_marks_skip_speak() -> None:
    from actions.tts_actions import TestDirectTtsAction
    from core.types import CommandRequest

    with patch("voice.pyttsx3_completion.run_direct_tts_isolated_test") as isolated:
        isolated.return_value = MagicMock(
            ok=True,
            elapsed_ms=1200.0,
            fallback_path="",
            error="",
            utterance_started=True,
            utterance_finished=True,
            completion_hang=False,
        )
        tts = TestDirectTtsAction().execute(
            CommandRequest(raw_text="test direct tts", intent=Intent.TEST_DIRECT_TTS)
        )
    assert tts.status == ActionStatus.SUCCESS
    assert tts.data.get("skip_speak") is True
    assert tts.data.get("already_spoken") is True
