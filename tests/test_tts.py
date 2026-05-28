"""TTS tests (no real audio output)."""

from unittest.mock import MagicMock, patch

import pytest

from config import TTS_MAX_CHARS
from core.app import JarvisApp
from core.types import ActionStatus, CommandResult, Intent
from voice.tts import TTSError, TTSService, resolve_tts_enabled, sanitize_for_speech


def test_tts_disabled_does_nothing():
    svc = TTSService(enabled=False)
    with patch.object(svc, "_speak_blocking") as speak:
        assert svc.speak("hello") is False
        speak.assert_not_called()


def test_tts_enabled_calls_engine():
    svc = TTSService(enabled=True)
    with patch.object(svc, "_speak_blocking", return_value=True) as speak:
        assert svc.speak("Opened Cursor.") is True
    speak.assert_called_once()


def test_long_summary_truncated():
    long = "x" * (TTS_MAX_CHARS + 100)
    safe = sanitize_for_speech(long)
    assert len(safe) <= TTS_MAX_CHARS
    assert safe.endswith("...")


def test_secrets_redacted_from_speech():
    text = "Done. API_KEY=supersecret123 and password=abc"
    safe = sanitize_for_speech(text)
    assert "supersecret123" not in safe
    assert "password=abc" not in safe.lower() or "[redacted]" in safe


def test_env_lines_removed():
    text = "OK\nOPENAI_API_KEY=sk-abcdef123456789012345678\nDone"
    safe = sanitize_for_speech(text)
    assert "sk-abcdef" not in safe


def test_resolve_tts_cli_overrides():
    assert resolve_tts_enabled(True) is True
    assert resolve_tts_enabled(False) is False


def test_tts_failure_does_not_fail_command():
    app = JarvisApp(speak_enabled=True)
    with (
        patch.object(app.tts, "speak", side_effect=TTSError("boom")),
        patch.object(app.router, "route") as route,
    ):
        route.return_value = CommandResult(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
        )
        result = app.handle_text_command("open cursor", print_result=False)
    assert result.status == ActionStatus.SUCCESS


def test_only_summary_spoken_not_data():
    app = JarvisApp(speak_enabled=True)
    with patch.object(app.tts, "speak") as speak:
        with patch.object(app.router, "route") as route:
            route.return_value = CommandResult(
                intent=Intent.OPEN_CURSOR,
                status=ActionStatus.SUCCESS,
                summary="Short summary.",
                data={"path": "C:\\secret\\path", "token": "hidden"},
            )
            app.handle_text_command("open cursor", print_result=False)
    spoken = speak.call_args[0][0]
    assert spoken == "Short summary."
    assert "hidden" not in spoken
    assert "secret" not in spoken


def test_sanitize_strips_rich_markup():
    safe = sanitize_for_speech("[bold]Hello[/] world")
    assert "[" not in safe
    assert "Hello" in safe
