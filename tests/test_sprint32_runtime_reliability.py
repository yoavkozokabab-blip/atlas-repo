"""Sprint 3.2 — runtime reliability (B02, B03, B04, B07)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.runtime_state import RuntimeState, reset_runtime_state
from core.thread_registry import ThreadRegistry, get_thread_registry


@pytest.fixture(autouse=True)
def _reset_runtime():
    from core.runtime_bootstrap import reset_runtime_bootstrap_for_tests
    from services.watchdog_runtime import stop_process_watchdog

    stop_process_watchdog()
    reset_runtime_bootstrap_for_tests()
    reset_runtime_state()
    yield
    stop_process_watchdog()
    reset_runtime_bootstrap_for_tests()
    reset_runtime_state()


def test_validate_config_returns_severity():
    from core.startup_validation import StartupValidationIssue, ValidationSeverity, validate_config

    with patch("config.IMPLEMENTED_INTENTS", new=None):
        issues = validate_config()
    assert issues
    assert all(isinstance(i, StartupValidationIssue) for i in issues)
    assert issues[0].severity == ValidationSeverity.CRITICAL


def test_critical_config_marks_runtime_degraded():
    from core.startup_validation import (
        apply_startup_validation_to_runtime,
        run_startup_validation,
    )

    runtime = RuntimeState()
    with patch("config.IMPLEMENTED_INTENTS", new=frozenset()):
        validation = run_startup_validation()
        apply_startup_validation_to_runtime(runtime, validation, print_summary=False)
    assert runtime.degraded is True
    assert runtime.degraded_reasons


def test_unwritable_data_dir_marks_runtime_degraded(monkeypatch):
    from core.startup_validation import (
        ValidationSeverity,
        apply_startup_validation_to_runtime,
        run_startup_validation,
    )

    original_write_text = Path.write_text

    def blocked_probe_write(self, *args, **kwargs):
        if self.name == ".startup_write_probe":
            raise OSError("mocked unwritable DATA_DIR")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", blocked_probe_write)
    with patch(
        "core.startup_validation.validate_win32_dependencies",
        return_value={"win32gui": True, "tesseract": True, "playwright": True},
    ):
        validation = run_startup_validation()

    data_dir_issues = [
        issue
        for issue in validation["issues"]
        if issue.check == "data_dir"
    ]
    assert data_dir_issues
    assert data_dir_issues[0].severity == ValidationSeverity.CRITICAL

    runtime = RuntimeState()
    apply_startup_validation_to_runtime(runtime, validation, print_summary=False)
    assert runtime.degraded is True
    assert "DATA_DIR" in runtime.degraded_reasons[0]


def test_missing_dependencies_mark_degraded_not_fatal(monkeypatch):
    from core.startup_validation import (
        ValidationSeverity,
        apply_startup_validation_to_runtime,
        run_startup_validation,
    )

    runtime = RuntimeState()
    with patch(
        "core.startup_validation.validate_win32_dependencies",
        return_value={"win32gui": False, "tesseract": False, "playwright": False},
    ):
        validation = run_startup_validation()
        apply_startup_validation_to_runtime(runtime, validation, print_summary=False)

    assert runtime.degraded is True
    assert validation["dependencies_missing"] == ["win32gui", "tesseract", "playwright"]
    warnings = [i for i in validation["issues"] if i.severity == ValidationSeverity.WARNING]
    assert len(warnings) >= 3


def test_startup_validation_runs_dependency_checks():
    from core.startup_validation import ValidationSeverity, run_startup_validation

    with patch(
        "core.startup_validation.validate_win32_dependencies",
        return_value={"win32gui": False, "tesseract": False, "playwright": True},
    ) as deps:
        validation = run_startup_validation()

    deps.assert_called_once()
    assert validation["dependencies_missing"] == ["win32gui", "tesseract"]
    warning_checks = {
        issue.check
        for issue in validation["issues"]
        if issue.severity == ValidationSeverity.WARNING
    }
    assert "dependency:win32gui" in warning_checks
    assert "dependency:tesseract" in warning_checks
    assert "dependency:playwright" not in warning_checks


def test_thread_registry_detects_dead_voice_and_tts():
    registry = ThreadRegistry()

    voice = threading.Thread(target=lambda: None, name="jarvis-voice", daemon=True)
    voice.start()
    voice.join(timeout=1.0)

    tts = threading.Thread(target=lambda: None, name="jarvis-tts", daemon=True)
    tts.start()
    tts.join(timeout=1.0)

    registry.register("jarvis-voice-loop", voice)
    registry.register("jarvis-tts", tts)
    time.sleep(0.05)

    dead = registry.heartbeat_check()
    assert "jarvis-voice-loop" in dead
    assert "jarvis-tts" in dead


def test_voice_loop_registers_liveness_fn():
    from core.app import JarvisApp
    from voice.voice_loop import run_voice_loop

    app = JarvisApp(skip_bootstrap=True)
    runtime = app.runtime
    runtime.set_voice(True)
    registry = get_thread_registry()

    def _stop_after_one(*_a, **_k):
        app._running = False
        return None

    with (
        patch("voice.voice_loop.record_until_enter", side_effect=_stop_after_one),
        patch.object(registry, "register_fn", wraps=registry.register_fn) as register_fn,
    ):
        run_voice_loop(app, runtime=runtime)

    register_fn.assert_called_once()
    assert register_fn.call_args[0][0] == "jarvis-voice-loop"


def test_tray_voice_thread_registered():
    from core.app import JarvisApp
    from ui.tray_app import JarvisTrayApp

    app = JarvisApp(skip_bootstrap=True)
    tray = JarvisTrayApp(app, start_wakeword_thread=False)

    def _fake_loop(*_a, **_k):
        time.sleep(0.2)

    with patch("voice.voice_loop.run_voice_loop", side_effect=_fake_loop):
        tray._start_voice_background()
        time.sleep(0.05)

    names = get_thread_registry().registered_names()
    assert "jarvis-voice-loop" in names
    tray.runtime.stop()
    app._running = False


def test_ensure_process_watchdog_idempotent():
    from services.watchdog_runtime import (
        ensure_process_watchdog,
        is_watchdog_running,
        stop_process_watchdog,
    )

    runtime = RuntimeState()
    with patch("services.watchdog.WatchdogService") as mock_cls:
        inst = MagicMock()
        thread = threading.Thread(target=lambda: time.sleep(2), daemon=True)
        thread.start()
        inst._thread = thread
        inst.start = MagicMock()
        inst.run_once = MagicMock(return_value={})
        inst.stop = MagicMock()
        mock_cls.return_value = inst

        ensure_process_watchdog(runtime=runtime)
        ensure_process_watchdog(runtime=runtime)
        assert mock_cls.call_count == 1
        assert is_watchdog_running()

    stop_process_watchdog()


def test_jarvis_app_startup_starts_watchdog_once():
    from core.app import JarvisApp
    from services.watchdog_runtime import get_process_watchdog, is_watchdog_running

    runtime = RuntimeState()
    release = threading.Event()

    def _wait_for_release():
        release.wait(timeout=2.0)

    with patch("services.watchdog.WatchdogService") as mock_cls:
        inst = MagicMock()
        thread = threading.Thread(
            target=_wait_for_release,
            name="jarvis-watchdog",
            daemon=True,
        )

        def _start():
            inst._thread = thread
            thread.start()

        def _stop():
            release.set()
            thread.join(timeout=1.0)

        inst._thread = None
        inst.start.side_effect = _start
        inst.stop.side_effect = _stop
        inst.run_once.return_value = {}
        mock_cls.return_value = inst

        JarvisApp(speak_enabled=False, runtime=runtime)
        JarvisApp(speak_enabled=False, runtime=runtime)

        assert mock_cls.call_count == 1
        assert get_process_watchdog() is inst
        assert is_watchdog_running() is True

    release.set()


def test_main_wires_process_watchdog():
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "main.py"
    text = source.read_text(encoding="utf-8")
    assert "ensure_process_watchdog" in text
    assert "safe_mode" in text
