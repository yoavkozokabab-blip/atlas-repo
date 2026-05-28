"""Backend verification and conversational playback fallback tests."""

from __future__ import annotations

from unittest.mock import patch

import config as cfg
from conversation.human_runtime import enable_human_conversational_runtime, reset_human_runtime_for_tests
from core.runtime_state import get_runtime_state
from core.types import Intent
from voice.audio_status import reset_audio_status
from voice.backend_verification import (
    conversational_playback_allowed,
    format_backend_verification_diagnostics,
    reset_backend_verification_for_tests,
)
from voice.tts_output_policy import evaluate_tts_output, reset_tts_output_policy_for_tests


def _setup(monkeypatch) -> None:
    reset_audio_status()
    reset_human_runtime_for_tests()
    reset_tts_output_policy_for_tests()
    reset_backend_verification_for_tests()
    get_runtime_state().speak_enabled = True
    monkeypatch.setattr(cfg, "TOOL_FIRST_MODE", True, raising=False)
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)
    enable_human_conversational_runtime()


def test_conversational_fallback_without_verified_metadata(monkeypatch):
    _setup(monkeypatch)

    with patch("voice.backend_verification.is_backend_initialized", return_value=True), patch(
        "voice.backend_verification.is_local_tts_synthesis_available",
        return_value=True,
    ):
        allowed, reason = conversational_playback_allowed(session_active=False)
        assert allowed is True
        assert reason == "conversational_runtime_local_fallback"

        decision = evaluate_tts_output(speak_enabled=True, voice_path="test")
        assert decision.allowed is True
        assert decision.reason == "conversational_runtime_local_fallback"


def test_session_active_allows_without_verified_metadata(monkeypatch):
    _setup(monkeypatch)
    from conversation.human_runtime import activate_session_for_tests

    activate_session_for_tests()

    with patch("voice.backend_verification.is_backend_initialized", return_value=True):
        allowed, reason = conversational_playback_allowed(session_active=True)
        assert allowed is True
        assert reason == "conversational_session_backend_ready"


def test_tool_first_still_blocks_without_conversational_runtime(monkeypatch):
    reset_audio_status()
    reset_human_runtime_for_tests()
    reset_tts_output_policy_for_tests()
    monkeypatch.setattr(cfg, "TOOL_FIRST_MODE", True, raising=False)
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", False, raising=False)

    decision = evaluate_tts_output(speak_enabled=True, voice_path="test")
    assert decision.allowed is False
    assert decision.reason == "tool_first_unverified_backend"


def test_backend_verification_diagnostics_format(monkeypatch):
    _setup(monkeypatch)
    with patch("voice.backend_verification.probe_backend", return_value=(True, "default", "")):
        text = format_backend_verification_diagnostics()
    assert "Backend verification diagnostics:" in text
    assert "pyttsx3:" in text
    assert "initialized: yes" in text


def test_test_tts_playback_command(monkeypatch):
    _setup(monkeypatch)
    from core.app import JarvisApp

    app = JarvisApp()
    with patch(
        "voice.backend_verification.run_tts_playback_self_test",
        return_value=type(
            "R",
            (),
            {
                "success": True,
                "backend": "pyttsx3",
                "device": "default",
                "elapsed_ms": 12.0,
                "error": "",
            },
        )(),
    ), patch(
        "voice.backend_verification.format_tts_playback_self_test_report",
        return_value="TTS playback self-test:\n  success: yes",
    ):
        result = app.handle_text_command("test tts playback", print_result=False)

    assert result.intent == Intent.TEST_TTS_PLAYBACK
    assert result.status.value == "success"
