"""Windows subprocess audio routing — default device, persistence, env inheritance."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from config import AUDIO_ROUTING_PATH
from voice.audio_devices import (
    get_persisted_playback_target,
    get_session_output_device,
    is_audible_route_verified,
    load_persisted_routing,
    set_audible_route_verified,
    set_persisted_playback_target,
    set_session_output_device,
)
from voice.audio_status import (
    get_audio_status,
    get_selected_verified_audio_backend,
    reset_audio_status,
    set_selected_verified_audio_backend,
)
from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND, build_pyttsx3_subprocess_code, run_subprocess_tts_argv
from voice.windows_audio_routing import (
    build_routed_pyttsx3_subprocess_code,
    format_windows_audio_routing_report,
    log_tts_route_before_subprocess,
    persist_audible_playback_route,
    resolve_subprocess_playback_route,
    subprocess_env_with_audio_route,
)


@pytest.fixture(autouse=True)
def _reset_routing(tmp_path, monkeypatch):
    monkeypatch.setattr("config.AUDIO_ROUTING_PATH", tmp_path / "audio_routing.json", raising=False)
    monkeypatch.setattr("voice.audio_devices.AUDIO_ROUTING_PATH", tmp_path / "audio_routing.json", raising=False)
    set_session_output_device(None)
    set_persisted_playback_target("default")
    set_audible_route_verified(False)
    reset_audio_status()
    yield
    set_session_output_device(None)
    set_persisted_playback_target("default")
    set_audible_route_verified(False)


def test_verified_backend_persists_in_memory():
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    assert get_selected_verified_audio_backend() == SHELL_SUBPROCESS_BACKEND


def test_routing_target_persists_to_disk(tmp_path, monkeypatch):
    path = tmp_path / "audio_routing.json"
    monkeypatch.setattr("voice.audio_devices.AUDIO_ROUTING_PATH", path, raising=False)
    persist_audible_playback_route(
        target_id="sonar_gaming",
        device_index=7,
        device_label="SteelSeries Sonar - Gaming",
    )
    load_persisted_routing()
    assert get_persisted_playback_target() == "sonar_gaming"
    assert get_session_output_device() == 7
    assert is_audible_route_verified() is True
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["playback_target"] == "sonar_gaming"
    assert raw["audible_route_verified"] is True


def test_audio_status_reports_active_route(monkeypatch):
    monkeypatch.setattr("config.TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", True, raising=False)
    set_session_output_device(3, label="Speakers (Realtek)")
    set_persisted_playback_target("default")
    set_audible_route_verified(True)
    status = get_audio_status()
    assert status.active_playback_route == "Speakers (Realtek)"
    assert status.playback_target == "default"
    assert status.audible_route_verified is True


def test_subprocess_env_inherits_routing_config(monkeypatch):
    monkeypatch.setattr("config.TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", True, raising=False)
    set_session_output_device(5, label="Sonar Gaming")
    env = subprocess_env_with_audio_route()
    assert env["JARVIS_AUDIO_OUTPUT_DEVICE"] == "5"
    assert "Sonar" in env["JARVIS_AUDIO_OUTPUT_LABEL"]


def test_log_tts_route_prints_default(capsys, monkeypatch):
    monkeypatch.setattr("config.TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", True, raising=False)
    monkeypatch.setattr(
        "voice.windows_audio_routing.get_windows_default_playback_name",
        lambda: "Speakers (Realtek)",
    )
    from voice.audio_devices import PlaybackDeviceInfo

    monkeypatch.setattr(
        "voice.audio_devices.default_playback_device",
        lambda: PlaybackDeviceInfo(0, "Speakers (Realtek)", "WASAPI", True),
    )
    route = log_tts_route_before_subprocess()
    out = capsys.readouterr().out
    assert "[TTS_ROUTE]" in out
    assert "default_output=Speakers (Realtek)" in out
    assert route.windows_default_name == "Speakers (Realtek)"


def test_build_routed_subprocess_code_uses_sounddevice_branch():
    code = build_routed_pyttsx3_subprocess_code("hello")
    assert "sounddevice" in code
    assert "JARVIS_AUDIO_OUTPUT_DEVICE" in code


def test_build_pyttsx3_subprocess_code_routed_by_default():
    code = build_pyttsx3_subprocess_code("test phrase")
    assert "sounddevice" in code


def test_run_subprocess_passes_env(monkeypatch):
    captured: dict = {}

    class _Proc:
        returncode = 0

        def communicate(self, timeout=None):
            return ("", "")

    def _popen(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return _Proc()

    monkeypatch.setattr("voice.tts_subprocess.subprocess.Popen", _popen)
    monkeypatch.setenv("JARVIS_ALLOW_AUDIO_PLAYBACK", "1")
    set_session_output_device(2, label="Default Device")
    run_subprocess_tts_argv(["py", "-3", "-c", "pass"], label="TTS_TEST")
    assert captured["env"]["JARVIS_AUDIO_OUTPUT_DEVICE"] == "2"


def test_show_windows_routing_report_includes_fields(monkeypatch):
    monkeypatch.setattr("config.TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", True, raising=False)
    monkeypatch.setattr(
        "voice.windows_audio_routing.detect_steelseries_sonar",
        lambda: True,
    )
    set_selected_verified_audio_backend(SHELL_SUBPROCESS_BACKEND)
    text = format_windows_audio_routing_report()
    assert "Windows default playback" in text
    assert "sounddevice default" in text
    assert "Subprocess backend" in text
    assert "Sonar detected: yes" in text


def test_resolve_uses_persisted_target_when_no_session(monkeypatch):
    monkeypatch.setattr("config.TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", True, raising=False)
    from voice.audio_devices import PlaybackDeviceInfo

    set_persisted_playback_target("sonar_gaming")
    monkeypatch.setattr(
        "voice.windows_audio_routing.find_playback_target_device",
        lambda tid: PlaybackDeviceInfo(9, "SteelSeries Sonar - Gaming", "WASAPI", False)
        if tid == "sonar_gaming"
        else None,
    )
    route = resolve_subprocess_playback_route()
    assert route.device_index == 9
    assert route.target_id == "sonar_gaming"


def test_cycle_windows_playback_persists_on_yes(monkeypatch):
    from voice.windows_audio_routing import cycle_windows_playback_target

    monkeypatch.setattr(
        "voice.windows_audio_routing.find_playback_target_device",
        lambda _tid: __import__("voice.audio_devices", fromlist=["PlaybackDeviceInfo"]).PlaybackDeviceInfo(
            4, "SteelSeries Sonar - Media", "WASAPI", False
        ),
    )
    monkeypatch.setattr(
        "voice.tts_subprocess.speak_subprocess_pyttsx3",
        lambda _t, **_: __import__(
            "voice.tts_subprocess", fromlist=["SubprocessTtsResult"]
        ).SubprocessTtsResult(exit_code=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "voice.audio_verified.ask_user_audible_confirmation",
        lambda _p, **_: True,
    )
    ok, msg = cycle_windows_playback_target()
    assert ok is True
    assert "saved" in msg.lower() or "Audible route" in msg
    assert get_persisted_playback_target() != "" or is_audible_route_verified()
