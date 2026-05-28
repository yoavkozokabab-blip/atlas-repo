"""Runtime defaults, startup flags, and show runtime status."""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from actions.runtime_actions import ShowRuntimeStatusAction
from brain.intent_classifier import classify_rules
from core.runtime_state import reset_runtime_state
from core.startup import print_runtime_config_flags
from core.types import ActionStatus, CommandRequest, Intent


@pytest.fixture(autouse=True)
def _reset():
    reset_runtime_state()
    yield
    reset_runtime_state()


def test_project_env_file_has_full_experience_defaults():
    """Local .env should enable voice/TTS/wake/overlay for ready-to-run tray."""
    from pathlib import Path

    env_path = Path(__file__).resolve().parent.parent / ".env"
    assert env_path.is_file()
    text = env_path.read_text(encoding="utf-8").lower()
    for key, value in (
        ("voice_enabled=true", "voice_enabled=true"),
        ("tts_enabled=true", "tts_enabled=true"),
        ("wake_word_enabled=true", "wake_word_enabled=true"),
        ("overlay_enabled=true", "overlay_enabled=true"),
        ("overlay_style=premium_ironman_full", "overlay_style=premium_ironman_full"),
        ("stt_language=en", "stt_language=en"),
        ("stt_enable_normalization=true", "stt_enable_normalization=true"),
    ):
        assert key in text, f"missing {value} in .env"


def test_print_runtime_config_flags(capsys, monkeypatch):
    monkeypatch.setattr("config.VOICE_ENABLED", True, raising=False)
    monkeypatch.setattr("config.TTS_ENABLED", True, raising=False)
    monkeypatch.setattr("config.WAKE_WORD_ENABLED", True, raising=False)
    monkeypatch.setattr("config.OVERLAY_ENABLED", True, raising=False)
    monkeypatch.setattr("config.OVERLAY_STYLE", "premium_ironman", raising=False)
    monkeypatch.setattr("config.STT_LANGUAGE", "en", raising=False)
    monkeypatch.setattr("config.STT_MODEL", "base", raising=False)
    print_runtime_config_flags()
    out = capsys.readouterr().out
    assert "VOICE_ENABLED=True" in out
    assert "OVERLAY_STYLE=premium_ironman" in out
    assert "STT_LANGUAGE=en" in out


def test_resolve_voice_from_config():
    import main

    args = argparse.Namespace(
        safe_mode=False,
        voice=False,
        wakeword=False,
        no_wakeword=False,
        speak=False,
        no_speak=False,
        overlay=False,
        no_overlay=False,
    )
    with patch("config.VOICE_ENABLED", True):
        enabled, cli = main._resolve_voice_flag(args)
    assert enabled is True
    assert cli is False


def test_cli_voice_overrides_false_config():
    import main

    args = argparse.Namespace(
        safe_mode=False,
        voice=True,
        wakeword=False,
        no_wakeword=False,
        speak=False,
        no_speak=False,
        overlay=False,
        no_overlay=False,
    )
    with patch("config.VOICE_ENABLED", False):
        enabled, cli = main._resolve_voice_flag(args)
    assert enabled is True
    assert cli is True


def test_classify_show_runtime_status():
    req = classify_rules("show runtime status")
    assert req.intent == Intent.SHOW_RUNTIME_STATUS


def test_show_runtime_status_action(monkeypatch):
    monkeypatch.setattr("config.VOICE_ENABLED", True, raising=False)
    monkeypatch.setattr("config.TTS_ENABLED", True, raising=False)
    monkeypatch.setattr("config.WAKE_WORD_ENABLED", True, raising=False)
    monkeypatch.setattr("config.OVERLAY_ENABLED", True, raising=False)
    from core.runtime_state import get_runtime_state

    rt = get_runtime_state()
    rt.set_voice(True)
    rt.set_speak(True)
    rt.set_wake_word(True)
    rt.set_overlay(True)

    result = ShowRuntimeStatusAction().execute(
        CommandRequest(raw_text="show runtime status", intent=Intent.SHOW_RUNTIME_STATUS)
    )
    assert result.status == ActionStatus.SUCCESS
    assert "VOICE_ENABLED=True" in result.summary
    assert "voice=True" in result.summary
    assert "overlay=True" in result.summary
