from __future__ import annotations


def test_runtime_config_mismatch_reports_stable_override(monkeypatch) -> None:
    from core import env_precedence

    env_precedence.reset_env_precedence_for_tests()
    monkeypatch.setattr(
        env_precedence,
        "_dotenv_file_values",
        {"VOICE_RUNTIME_MODE": "stable", "STT_STREAMING_BUFFER_ENABLED": "true"},
        raising=False,
    )
    monkeypatch.setattr(env_precedence, "_resolved_env", {}, raising=False)

    import config as cfg

    monkeypatch.setattr(cfg, "VOICE_RUNTIME_MODE", "stable", raising=False)
    monkeypatch.setattr(cfg, "STT_STREAMING_BUFFER_ENABLED", False, raising=False)

    body = env_precedence.format_runtime_config_mismatches().lower()
    assert "stt_streaming_buffer_enabled mismatch" in body
    assert "forced off by stable mode override" in body


def test_tts_startup_self_test_marks_verified_local_backend(monkeypatch) -> None:
    import config as cfg
    from voice.audio_status import get_selected_verified_audio_backend, reset_audio_status
    from voice.tts_startup import run_tts_startup_self_test

    reset_audio_status()
    monkeypatch.setattr(cfg, "TTS_STARTUP_SELF_TEST", True, raising=False)
    monkeypatch.setattr(cfg, "TTS_ENGINE", "pyttsx3", raising=False)
    monkeypatch.setattr("voice.audio_verified.has_verified_audio_backend", lambda: True)
    monkeypatch.setattr("voice.tts.TTSService.speak", lambda self, phrase: True)
    monkeypatch.setattr("voice.audio_devices.load_persisted_routing", lambda: None)
    monkeypatch.setattr("voice.audio_devices.log_startup_audio_devices", lambda: None)
    monkeypatch.setattr("voice.audio_status.probe_output_device", lambda: "test-device")

    run_tts_startup_self_test(enabled=True)
    assert get_selected_verified_audio_backend() == "verified_local_pyttsx3"

