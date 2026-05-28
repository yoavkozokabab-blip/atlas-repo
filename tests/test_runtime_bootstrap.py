"""Runtime bootstrap — JarvisApp must load env-backed speak/conversational state."""

from __future__ import annotations

from unittest.mock import patch

import config as cfg
from conversation.human_runtime import (
    is_human_conversational_runtime_enabled,
    reset_human_runtime_for_tests,
    uses_continuous_conversation,
)
from core.app import JarvisApp
from core.runtime_bootstrap import (
    format_show_tts_debug,
    is_runtime_bootstrapped,
    reset_runtime_bootstrap_for_tests,
)
from core.runtime_state import RuntimeState, reset_runtime_state
from core.types import Intent
from voice.tts_output_policy import evaluate_tts_output


def _reset() -> None:
    reset_runtime_state()
    reset_runtime_bootstrap_for_tests()
    reset_human_runtime_for_tests()


def test_jarvis_app_bootstraps_speak_from_config(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "TTS_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "TOOL_FIRST_MODE", False, raising=False)

    app = JarvisApp()

    assert is_runtime_bootstrapped()
    assert app.speak_enabled is True
    decision = evaluate_tts_output(speak_enabled=app.speak_enabled, voice_path="test")
    assert decision.allowed is True


def test_jarvis_app_bootstraps_conversational_runtime(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)

    JarvisApp()

    assert is_human_conversational_runtime_enabled()
    assert uses_continuous_conversation()


def test_jarvis_app_respects_explicit_speak_override(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "TTS_ENABLED", True, raising=False)

    app = JarvisApp(speak_enabled=False)

    assert app.speak_enabled is False


def test_show_tts_debug_command(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "TTS_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)

    app = JarvisApp()
    with patch.object(app.tts, "speak"):
        result = app.handle_text_command("show tts debug", print_result=False)

    assert result.status.value == "success"
    assert result.intent == Intent.SHOW_TTS_DEBUG
    assert "speak_enabled: yes" in result.summary
    assert "bootstrap applied: yes" in result.summary
    assert "conversational runtime enabled: yes" in result.summary


def test_show_conversation_runtime_after_bootstrap(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "HUMAN_CONVERSATIONAL_RUNTIME_ENABLED", True, raising=False)
    monkeypatch.setattr(cfg, "CONVERSATION_CONTINUOUS_MIC_ENABLED", True, raising=False)

    app = JarvisApp()
    with patch.object(app.tts, "speak"):
        result = app.handle_text_command("show conversation runtime", print_result=False)

    assert result.status.value == "success"
    assert "enabled: yes" in result.summary
    assert "continuous mic: yes" in result.summary


def test_format_show_tts_debug_reports_muted_when_disabled(monkeypatch):
    _reset()
    monkeypatch.setattr(cfg, "TTS_ENABLED", False, raising=False)

    app = JarvisApp(speak_enabled=False, skip_bootstrap=True)

    text = format_show_tts_debug(runtime=app.runtime)
    assert "speak_enabled: no" in text
    assert "muted: yes" in text
