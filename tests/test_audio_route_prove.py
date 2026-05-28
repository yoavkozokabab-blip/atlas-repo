"""Hard audio route prove — user-confirmed A/B playback tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from actions.voice_audio_actions import AudioRouteProveAction, ForceDirectPyttsx3NormalModeAction
from core.types import ActionStatus, CommandRequest, Intent
from voice.audio_route_prove import (
    parse_yes_no,
    resolve_verified_backend_from_user_results,
    run_audio_route_prove,
)
from voice.audio_status import (
    format_audio_status,
    get_audio_status,
    is_force_direct_normal_mode,
    reset_audio_status,
    user_confirmed_direct_audio,
)
from voice.tts_pyttsx3 import NORMAL_DIRECT_SPEAKER, speak_pyttsx3_direct


@pytest.fixture(autouse=True)
def _reset():
    reset_audio_status()
    yield
    reset_audio_status()


def test_parse_yes_no():
    assert parse_yes_no("yes") is True
    assert parse_yes_no("NO") is False
    assert parse_yes_no("maybe") is None


def test_resolve_verified_backend_only_direct():
    assert (
        resolve_verified_backend_from_user_results(
            direct=True,
            winsound=False,
            wav_winsound=False,
            sounddevice=False,
        )
        == "direct_pyttsx3"
    )


def test_normal_direct_speaker_same_object():
    assert NORMAL_DIRECT_SPEAKER is speak_pyttsx3_direct


def test_run_audio_route_prove_records_user_heard(monkeypatch):
    heard = {1: True, 2: False, 3: False, 4: False}
    monkeypatch.setattr(
        "voice.audio_route_prove.ask_user_heard_test",
        lambda n, **_: heard.get(n),
    )
    monkeypatch.setattr(
        "voice.audio_route_prove.prove_test1_direct_pyttsx3",
        lambda: (True, ""),
    )
    monkeypatch.setattr(
        "voice.audio_route_prove.prove_test2_winsound_beep",
        lambda: (True, ""),
    )
    monkeypatch.setattr(
        "voice.audio_route_prove.prove_test3_wav_winsound",
        lambda: (True, ""),
    )
    monkeypatch.setattr(
        "voice.audio_route_prove.prove_test4_wav_sounddevice",
        lambda: (True, ""),
    )
    monkeypatch.setattr("voice.audio_route_prove._gap", lambda *_a, **_k: None)

    report = run_audio_route_prove(gap_seconds=0)
    assert report.selected_backend == "direct_pyttsx3"
    status = get_audio_status()
    assert status.direct_pyttsx3_user_heard is True
    assert status.winsound_user_heard is False
    assert user_confirmed_direct_audio() is True


def test_engine_complete_does_not_set_user_success(monkeypatch):
    monkeypatch.setattr("pyttsx3.init", lambda: MagicMock())
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    from voice.tts_pyttsx3 import reset_pyttsx3_engine

    reset_pyttsx3_engine()
    NORMAL_DIRECT_SPEAKER("x", rate_raw="", record_user_success=False)
    status = get_audio_status()
    assert status.direct_engine_last_completed_at is not None
    assert status.direct_pyttsx3_user_heard is None
    assert status.direct_speech_last_success_at is None


def test_force_direct_action():
    result = ForceDirectPyttsx3NormalModeAction().execute(
        CommandRequest(
            raw_text="force direct pyttsx3 normal mode",
            intent=Intent.FORCE_DIRECT_PYTTSX3_NORMAL_MODE,
        )
    )
    assert result.status == ActionStatus.SUCCESS
    assert is_force_direct_normal_mode() is True
    assert "NORMAL_DIRECT_SPEAKER is speak_pyttsx3_direct: True" in result.summary


def test_audio_route_prove_action():
    with patch("voice.audio_route_prove.run_audio_route_prove") as run:
        run.return_value = MagicMock(
            summary="ok",
            selected_backend="direct_pyttsx3",
            steps=[],
        )
        result = AudioRouteProveAction().execute(
            CommandRequest(raw_text="audio route prove", intent=Intent.AUDIO_ROUTE_PROVE)
        )
    assert result.status == ActionStatus.SUCCESS
    run.assert_called_once()


def test_format_audio_status_user_fields():
    from voice.audio_status import record_user_heard_result

    record_user_heard_result("direct_pyttsx3", True)
    text = format_audio_status()
    assert "Direct pyttsx3 user heard: yes" in text
    assert "Selected verified audio backend: none" in text or "direct_pyttsx3" in text
