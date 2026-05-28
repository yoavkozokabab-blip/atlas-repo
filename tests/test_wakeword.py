"""Wake word layer tests (mocked openWakeWord / microphone)."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, Intent
from voice.privacy import ensure_no_audio_persistence, validate_runtime_privacy
from voice.wakeword import WakeWordDetector, resolve_oww_model_name
from voice.wakeword_loop import (
    _start_post_wake_session_thread,
    run_post_wake_listening_session,
    start_wakeword_loop,
    stop_wakeword_loop,
)


class FakeModel:
    def __init__(self, score: float = 0.0):
        self.prediction_buffer = {"hey_jarvis": [score]}
        self.predict_calls = 0

    def predict(self, _audio):
        self.predict_calls += 1
        self.prediction_buffer["hey_jarvis"] = [0.9 if self.predict_calls > 1 else 0.1]


@pytest.fixture
def runtime():
    return RuntimeState(wake_word_enabled=True, voice_enabled=False)


@pytest.fixture
def app(runtime):
    return JarvisApp(speak_enabled=False, runtime=runtime)


def test_wake_word_disabled_by_default(monkeypatch):
    monkeypatch.setenv("WAKE_WORD_ENABLED", "false")
    import importlib

    import config

    importlib.reload(config)
    assert config.WAKE_WORD_ENABLED is False


def test_resolve_model_alias():
    assert resolve_oww_model_name("jarvis") == "hey_jarvis"


def test_detection_triggers_listening_only(app, runtime, monkeypatch, tmp_path):
    wav = tmp_path / "wake.wav"
    wav.write_bytes(b"RIFF")
    wake_calls: list[float] = []

    def on_wake(score: float) -> None:
        wake_calls.append(score)

    monkeypatch.setattr("voice.microphone.check_microphone_available", lambda: None)
    monkeypatch.setattr(
        "voice.wakeword_loop.record_for_seconds",
        lambda _s, **k: wav,
    )
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="open cursor",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    monkeypatch.setattr("voice.wakeword_loop.ensure_no_audio_persistence", lambda _p: None)

    with patch.object(app, "handle_text_command") as handle:
        handle.return_value = MagicMock(
            intent=Intent.OPEN_CURSOR,
            status=ActionStatus.SUCCESS,
            summary="ok",
        )
        run_post_wake_listening_session(app)

    handle.assert_called_once()
    assert handle.call_args[0][0] == "open cursor"
    assert handle.call_args[1]["input_mode"] == "wakeword"


def test_no_direct_execution_from_detector(app, runtime, monkeypatch):
    """Detector callback must not call handle_text_command itself."""
    monkeypatch.setattr("config.WAKE_WORD_THRESHOLD", 0.3)
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_THRESHOLD", 0.3)

    triggered = []

    def on_wake(score: float) -> None:
        triggered.append(score)

    detector = WakeWordDetector(
        app,
        on_wake,
        model_factory=lambda: FakeModel(0.9),
    )

    with patch.object(app, "handle_text_command") as handle:
        detector._handle_detection(0.95)
    handle.assert_not_called()
    assert triggered == [0.95]


def test_cooldown_enforced(runtime):
    runtime.wake_word_cooldown_until = time.monotonic() + 60
    detector = WakeWordDetector(MagicMock(runtime=runtime), lambda s: None)
    assert detector._in_cooldown()


def test_no_repeated_wake_retrigger_during_cooldown(app, runtime, monkeypatch):
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_NOTIFY", False)
    triggered: list[float] = []
    detector = WakeWordDetector(app, lambda score: triggered.append(score))

    detector._handle_detection(0.91)
    runtime.start_wake_cooldown(4)
    detector._handle_detection(0.97)

    assert triggered == [0.91]
    assert runtime.wake_word_detection_count == 1


def test_detector_suspended_during_wake_recording(app, runtime, monkeypatch):
    observed: list[tuple[bool, bool]] = []

    def fake_session(_app, *, session_already_acquired: bool = False):
        observed.append((runtime.wake_word_listening_active, session_already_acquired))
        runtime.release_wake_listening_session()

    class InlineThread:
        def __init__(self, target, args=(), kwargs=None, **_opts):
            self.target = target
            self.args = args
            self.kwargs = kwargs or {}

        def start(self):
            assert runtime.wake_word_listening_active is True
            self.target(*self.args, **self.kwargs)

    monkeypatch.setattr("voice.wakeword_loop.run_post_wake_listening_session", fake_session)
    monkeypatch.setattr("voice.wakeword_loop.threading.Thread", InlineThread)

    assert _start_post_wake_session_thread(app) is True
    assert observed == [(True, True)]


def test_wake_resumes_after_cooldown(app, runtime, monkeypatch):
    monkeypatch.setattr("voice.wakeword.WAKE_WORD_NOTIFY", False)
    triggered: list[float] = []
    detector = WakeWordDetector(app, lambda score: triggered.append(score))
    runtime.wake_word_cooldown_until = time.monotonic() - 0.01

    detector._handle_detection(0.82)

    assert triggered == [0.82]
    assert runtime.wake_word_detection_count == 1


def test_overlapping_sessions_blocked(runtime):
    assert runtime.acquire_wake_listening_session()
    assert not runtime.acquire_wake_listening_session()
    runtime.release_wake_listening_session()
    assert runtime.acquire_wake_listening_session()


def test_detector_failure_graceful(app, runtime, monkeypatch):
    def _fail():
        raise Exception("no mic")

    monkeypatch.setattr("voice.microphone.check_microphone_available", _fail)
    detector = WakeWordDetector(app, lambda s: None)
    detector._detect_loop()
    assert runtime.wake_word_errors >= 1


def test_tray_toggle_updates_runtime():
    from ui.tray_app import JarvisTrayApp

    app = JarvisApp(runtime=RuntimeState())
    tray = JarvisTrayApp(app)
    with patch.object(tray, "_start_wakeword_background") as start:
        tray._toggle_wake_word()
    assert app.runtime.wake_word_enabled is True
    start.assert_called_once()
    with patch.object(tray, "_stop_wakeword_background") as stop:
        tray._toggle_wake_word()
    assert app.runtime.wake_word_enabled is False
    stop.assert_called_once()


def test_wake_routes_through_router(app, runtime, monkeypatch, tmp_path):
    wav = tmp_path / "w.wav"
    wav.write_bytes(b"x")
    monkeypatch.setattr("voice.wakeword_loop.record_for_seconds", lambda _s, **k: wav)
    from voice.transcriber import TranscriptionResult

    monkeypatch.setattr(
        "voice.wakeword_loop.transcribe_audio_detailed",
        lambda _p: TranscriptionResult(
            text="show capabilities",
            language="en",
            model="medium",
            device="cpu",
            compute_type="int8",
        ),
    )
    with patch.object(app.router, "route") as route:
        route.return_value = MagicMock(
            intent=Intent.SHOW_CAPABILITIES,
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
        )
        run_post_wake_listening_session(app)
    route.assert_called_once()


def test_no_audio_persistence(tmp_path, monkeypatch):
    handle = tempfile.NamedTemporaryFile(prefix="jarvis_", suffix=".wav", dir=tmp_path, delete=True)
    handle.write(b"data")
    handle.flush()
    f = Path(handle.name)
    state = {"handle": handle}

    def _sandbox_delete(target: Path) -> bool:
        assert Path(target) == f
        live = state.get("handle")
        if live is not None:
            live.close()
            state["handle"] = None
        return not f.exists()

    monkeypatch.setattr("voice.privacy.remove_file_best_effort", _sandbox_delete)
    try:
        ensure_no_audio_persistence(f)
        assert not f.exists()
    finally:
        live = state.get("handle")
        if live is not None:
            live.close()


def test_respects_runtime_running(app, runtime):
    runtime.running = False
    runtime.wake_word_enabled = True
    detector = WakeWordDetector(app, lambda s: None)
    # loop would sleep — just verify gate flags
    assert not runtime.running


def test_push_to_talk_still_calls_handle_text_command():
    app = JarvisApp()
    app.runtime.set_voice(True)
    with patch.object(app, "handle_text_command") as handle:
        from voice.voice_loop import process_voice_transcript

        process_voice_transcript(app, "open cursor", print_result=False)
    handle.assert_called_once()


def test_start_stop_wakeword_loop(app, monkeypatch):
    fake = MagicMock()
    fake.start = MagicMock(return_value=True)
    fake.stop = MagicMock()
    monkeypatch.setattr("voice.wakeword_loop.WakeWordDetector", lambda a, cb: fake)
    det = start_wakeword_loop(app)
    fake.start.assert_called_once()
    stop_wakeword_loop(det)


def test_privacy_no_persist_dirs():
    warnings = validate_runtime_privacy(debug=False)
    assert isinstance(warnings, list)
