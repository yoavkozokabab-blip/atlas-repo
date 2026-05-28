"""Phase A1 runtime stability coverage."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.runtime_monitor import get_runtime_monitor, reset_runtime_monitor, run_with_timeout


@pytest.fixture(autouse=True)
def _reset_monitor(tmp_path, monkeypatch):
    monitor = get_runtime_monitor()
    monitor.stop()
    reset_runtime_monitor()
    monitor.status_path = tmp_path / "runtime_monitor_status.json"
    yield
    monitor.stop()
    reset_runtime_monitor()
    from config import RUNTIME_MONITOR_STATUS_PATH

    monitor.status_path = RUNTIME_MONITOR_STATUS_PATH


def test_runtime_monitor_flags_stuck_operation():
    monitor = get_runtime_monitor()
    token = monitor.begin_operation("test.stuck", timeout_seconds=0.001)
    try:
        time.sleep(0.02)
        status = monitor.run_once()
    finally:
        monitor.end_operation(token)

    assert status["overall"] == "critical"
    assert any(i["source"] == "operation_timeout" for i in status["issues"])
    assert status["threads"]["jarvis_total"] >= 0
    assert "memory" in status


def test_run_with_timeout_returns_before_blocking_operation():
    def slow():
        time.sleep(0.2)
        return "late"

    with pytest.raises(TimeoutError):
        run_with_timeout("test.timeout", 0.01, slow)

    status = get_runtime_monitor().run_once()
    assert any(t["name"] == "test.timeout" for t in status["timeouts"])


def test_stt_timeout_resets_model_cache(monkeypatch, tmp_path: Path):
    import config
    import voice.transcriber as transcriber
    from voice.transcriber import TranscriptionError

    monkeypatch.setattr(config, "STT_TIMEOUT_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(
        transcriber,
        "_transcribe_audio_detailed_inner",
        lambda _path: (time.sleep(0.2), None)[1],
    )
    reset_called: list[bool] = []
    monkeypatch.setattr(transcriber, "reset_model_cache", lambda: reset_called.append(True))

    with pytest.raises(TranscriptionError, match="STT timeout"):
        transcriber.transcribe_audio_detailed(tmp_path / "sample.wav")

    assert reset_called
    status = get_runtime_monitor().run_once()
    assert any(t["name"] == "stt.transcribe" for t in status["timeouts"])


def test_tts_timeout_resets_engine(monkeypatch):
    import config
    from voice.tts import TTSError, TTSService

    monkeypatch.setattr(config, "TTS_ASYNC", False, raising=False)
    monkeypatch.setattr(config, "TTS_TIMEOUT_SECONDS", 0.01, raising=False)
    svc = TTSService(enabled=True)
    monkeypatch.setattr(svc, "_speak_blocking", lambda _safe: (time.sleep(0.2), True)[1])
    reset_called: list[bool] = []
    monkeypatch.setattr(svc, "reset_engine", lambda: reset_called.append(True))

    with pytest.raises(TTSError, match="TTS timeout"):
        svc.speak("hello")

    assert reset_called
    status = get_runtime_monitor().run_once()
    assert any(t["name"] == "tts.speak" for t in status["timeouts"])


def test_overlay_recover_if_crashed_restarts_thread(monkeypatch):
    from ui.overlay_app import OverlayController

    monkeypatch.setattr("ui.overlay_app.OVERLAY_QT_ENABLED", True)
    monkeypatch.setattr("ui.overlay_app._runtime_overlay_enabled", lambda: True)
    starts: list[str] = []

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True
            starts.append(self.name)

        def is_alive(self):
            return self.started

    ctrl = OverlayController()
    ctrl._enabled = True
    ctrl._qt_thread = MagicMock(is_alive=lambda: False)
    ctrl._ready.set()
    monkeypatch.setattr("ui.overlay_app.threading.Thread", FakeThread)

    assert ctrl.recover_if_crashed(reason="test_crash") is True
    assert starts == ["jarvis-overlay-qt"]


def test_watchdog_records_in_process_recovery(tmp_path: Path):
    from services.health import HealthReport
    from services.watchdog import WatchdogService

    tray = MagicMock()
    tray.runtime = MagicMock(running=True, voice_enabled=True, tray_enabled=True, last_error=None)
    tray._voice_thread = None
    tray._icon = None
    tray.restart_background_services.return_value = [
        {
            "component": "voice",
            "action": "restart_thread",
            "ok": True,
            "reason": "watchdog",
        }
    ]
    report = HealthReport(overall="ok", summary="ok", checked_at="t")

    with patch("services.watchdog.run_jarvis_health_check", return_value=report):
        payload = WatchdogService(tray, status_path=tmp_path / "watchdog.json").run_once()

    assert payload["repairs_performed"] is True
    assert payload["recoveries"][0]["component"] == "voice"
    assert "runtime_monitor" in payload
