"""Voice pipeline tests (no real microphone)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.types import ActionStatus, CommandResult, Intent
from voice.transcriber import TranscriptionResult
from voice.voice_loop import run_voice_loop


def _stt(text: str, *, low_confidence: bool = False) -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="en",
        model="medium",
        device="cpu",
        compute_type="int8",
        low_confidence=low_confidence,
    )


def test_handle_text_command_uses_router():
    app = JarvisApp()
    with patch.object(app.router, "route") as route:
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="ok",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        app.handle_text_command("open cursor", input_mode="text", print_result=False)
    route.assert_called_once_with("open cursor", input_mode="text", transcribed_text=None)


def test_voice_command_logs_input_mode(tmp_path: Path, monkeypatch):
    history = tmp_path / "history.jsonl"
    monkeypatch.setattr("config.COMMAND_HISTORY_PATH", history)
    monkeypatch.setattr("brain.router.COMMAND_HISTORY_PATH", history)

    app = JarvisApp()
    with patch("actions.apps.subprocess.Popen"):
        app.handle_text_command(
            "open cursor",
            input_mode="voice",
            transcribed_text="open cursor",
            print_result=False,
        )

    lines = history.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    entry = json.loads(lines[-1])
    assert entry["input_mode"] == "voice"
    assert entry["transcribed_text"] == "open cursor"


def test_empty_transcript_not_executed():
    app = JarvisApp()
    with patch.object(app.router, "route") as route:
        result = app.handle_text_command("   ", input_mode="voice", print_result=False)
    route.assert_not_called()
    assert result.status == ActionStatus.BLOCKED


def test_voice_loop_hebrew_through_router(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")

    app = JarvisApp()
    app._running = True
    app.runtime.set_voice(True)

    def fake_record():
        app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=fake_record),
        patch("voice.voice_loop.transcribe_audio_detailed", return_value=_stt("פתח קרסור")),
        patch.object(app.router, "route") as route,
    ):
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        run_voice_loop(app)

    route.assert_called_once()
    assert route.call_args[0][0] == "פתח קרסור"
    assert route.call_args[1]["input_mode"] == "voice"


def test_voice_loop_records_stt_latency_before_routing(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")
    app = JarvisApp(speak_enabled=False)
    app._running = True
    app.runtime.set_voice(True)

    def fake_record():
        app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=fake_record),
        patch("voice.voice_loop.transcribe_audio_detailed", return_value=_stt("open cursor")),
        patch("voice.voice_loop.record_stt_result") as record_stt,
        patch.object(app.router, "route") as route,
    ):
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        run_voice_loop(app)

    record_stt.assert_called_once()
    _, kwargs = record_stt.call_args
    assert kwargs["transcribe_ms"] >= 0.0
    assert kwargs["empty"] is False
    assert kwargs["raw_text"] == "open cursor"
    assert kwargs["normalized_text"] == "open cursor"
    route.assert_called_once()


def test_voice_loop_low_confidence_notifies_and_still_routes_final(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")
    app = JarvisApp(speak_enabled=False)
    app._running = True
    app.runtime.set_voice(True)
    app.runtime.set_overlay(True)

    def fake_record():
        app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=fake_record),
        patch(
            "voice.voice_loop.transcribe_audio_detailed",
            return_value=_stt("open cursor", low_confidence=True),
        ),
        patch("voice.voice_loop.notify_low_confidence") as notify_low,
        patch.object(app.router, "route") as route,
    ):
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        run_voice_loop(app)

    notify_low.assert_called_once_with(
        app,
        overlay_enabled=True,
        speak_prompt=False,
    )
    route.assert_called_once()


def test_voice_loop_empty_transcript_skips_router(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"x")
    app = JarvisApp()
    app._running = True
    app.runtime.set_voice(True)
    calls = {"n": 0}

    def stop_after_two():
        calls["n"] += 1
        if calls["n"] >= 2:
            app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=stop_after_two),
        patch("voice.voice_loop.transcribe_audio_detailed", return_value=_stt("   ")),
        patch.object(app.router, "route") as route,
    ):
        run_voice_loop(app)

    route.assert_not_called()


def test_voice_cannot_bypass_security():
    """Voice text still goes through validate_intent; unknown stays blocked."""
    app = JarvisApp()
    result = app.handle_text_command(
        "completely unknown xyz command",
        input_mode="voice",
        transcribed_text="completely unknown xyz command",
        print_result=False,
    )
    assert result.status in (
        ActionStatus.BLOCKED,
        ActionStatus.CLARIFICATION_NEEDED,
    )


def test_voice_confirmation_still_required():
    app = JarvisApp()
    result = app.handle_text_command(
        "run live daily loop",
        input_mode="voice",
        print_result=False,
    )
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert result.requires_confirmation


def test_voice_without_speak_does_not_call_tts(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")
    app = JarvisApp(speak_enabled=False)
    app._running = True
    app.runtime.set_voice(True)

    def fake_record():
        app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=fake_record),
        patch("voice.voice_loop.transcribe_audio_detailed", return_value=_stt("open cursor")),
        patch.object(app.tts, "speak") as speak,
        patch.object(app.router, "route") as route,
    ):
        route.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
            data={},
            error=None,
            requires_confirmation=False,
            confirmation_id=None,
            next_suggestions=[],
        )
        run_voice_loop(app)

    speak.assert_not_called()


def test_voice_with_speak_calls_tts_after_result(tmp_path: Path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF")
    app = JarvisApp(speak_enabled=True)
    app._running = True
    app.runtime.set_voice(True)

    def fake_record():
        app._running = False
        return wav

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=fake_record),
        patch("voice.voice_loop.transcribe_audio_detailed", return_value=_stt("open cursor")),
        patch.object(app.tts, "speak") as speak,
        patch.object(app.router, "route") as route,
    ):
        route.return_value = CommandResult(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="Opened Cursor.",
        )
        run_voice_loop(app)

    speak.assert_called_once_with("Opened Cursor.")
