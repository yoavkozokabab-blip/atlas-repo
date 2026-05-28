"""Startup modes, diagnostics, smoke, and tray blocking."""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.runtime_state import reset_runtime_state
from core.startup import (
    ENV_EXAMPLE,
    ENV_FILE,
    PROJECT_ROOT,
    _safe_config_snapshot,
    check_env_file,
    describe_modes,
    run_smoke_test,
)


@pytest.fixture(autouse=True)
def _reset_runtime(monkeypatch):
    reset_runtime_state()
    monkeypatch.setattr("core.startup.is_windows_store_python_stub", lambda: False)
    monkeypatch.setattr(
        "core.startup.probe_optional_imports",
        lambda print_results=True: {},
    )
    yield
    reset_runtime_state()


def _args(**kwargs) -> argparse.Namespace:
    defaults = {
        "text": False,
        "voice": False,
        "tray": False,
        "no_tray": False,
        "hotkey": False,
        "speak": False,
        "no_speak": False,
        "wakeword": False,
        "no_wakeword": False,
        "debug_startup": False,
        "smoke": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_describe_modes_tray_wakeword():
    assert "tray" in describe_modes(_args(tray=True, wakeword=True))
    assert "wakeword" in describe_modes(_args(tray=True, wakeword=True))


def test_missing_env_warning(tmp_path, capsys):
    env = tmp_path / ".env"
    example = tmp_path / ".env.example"
    example.write_text("WAKE_WORD_ENABLED=false\n", encoding="utf-8")
    with patch("core.startup.ENV_FILE", env), patch("core.startup.ENV_EXAMPLE", example):
        assert check_env_file() is False
    out = capsys.readouterr().out
    assert ".env not found" in out
    assert ".env.example" in out


def test_safe_config_snapshot_redacts_secrets(monkeypatch):
    import config

    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-secret", raising=False)
    snap = _safe_config_snapshot()
    for val in snap.values():
        assert "sk-secret" not in str(val)
    if "OPENAI_API_KEY" in snap:
        assert snap["OPENAI_API_KEY"] == "[redacted]"


def test_smoke_reports_components(capsys):
    with (
        patch("core.startup.ENV_FILE", PROJECT_ROOT / ".env"),
        patch("core.startup._try_check", side_effect=lambda _l, fn: (True, "ok")),
    ):
        code = run_smoke_test()
    out = capsys.readouterr().out
    assert "[PASS]" in out or "[FAIL]" in out
    assert "pystray import" in out
    assert "Smoke overall:" in out
    assert code in (0, 1)


def test_wakeword_cli_override_message(capsys, monkeypatch):
    monkeypatch.setattr("config.WAKE_WORD_ENABLED", False, raising=False)
    argv = ["main.py", "--tray", "--wakeword", "--speak"]
    mock_tray = MagicMock()

    with (
        patch.object(sys, "argv", argv),
        patch("core.startup.probe_optional_imports", return_value={}),
        patch("core.startup.is_windows_store_python_stub", return_value=False),
        patch("ui.tray_app.JarvisTrayApp", return_value=mock_tray),
        patch("core.app.JarvisApp") as MockApp,
    ):
        MockApp.return_value.speak_enabled = True
        MockApp.return_value.runtime.wake_word_enabled = True
        import main

        code = main.main()

    assert code == 0
    mock_tray.start.assert_called_once()
    out = capsys.readouterr().out
    assert "Wake word enabled by CLI flag" in out
    assert "JARVIS STARTUP" in out


def test_tray_path_calls_blocking_start():
    from core.app import JarvisApp
    from core.runtime_state import RuntimeState
    from ui.tray_app import JarvisTrayApp

    runtime = RuntimeState()
    app = JarvisApp(speak_enabled=False, runtime=runtime)
    tray = JarvisTrayApp(app, start_wakeword_thread=False, start_voice_thread=False)

    mock_icon = MagicMock()
    run_called: list[bool] = []

    def fake_run():
        run_called.append(True)
        runtime.stop()
        app._running = False

    mock_icon.run = MagicMock(side_effect=fake_run)

    fake_pystray = MagicMock()
    fake_pystray.Icon.return_value = mock_icon
    with (
        patch.dict(sys.modules, {"pystray": fake_pystray}),
        patch("ui.tray_app._create_icon_image"),
        patch("services.watchdog.WatchdogService") as wdog,
    ):
        wdog.return_value.start.return_value = None
        wdog.return_value.run_once.return_value = None
        tray.start()

    assert run_called
    mock_icon.run.assert_called_once()
    assert runtime.running is False


def test_tray_pystray_import_failure_exits_clear():
    from core.app import JarvisApp
    from core.runtime_state import RuntimeState
    from core.startup import StartupError
    from ui.tray_app import JarvisTrayApp

    runtime = RuntimeState()
    app = JarvisApp(speak_enabled=False, runtime=runtime)
    tray = JarvisTrayApp(app)

    import builtins

    real_import = builtins.__import__

    def _block_pystray(name, *a, **kw):
        if name == "pystray" or (isinstance(name, str) and name.startswith("pystray.")):
            raise ImportError("no pystray")
        return real_import(name, *a, **kw)

    with patch.object(builtins, "__import__", side_effect=_block_pystray):
        with pytest.raises(StartupError, match="pystray"):
            tray.start()


def test_wakeword_failure_does_not_prevent_tray_run(capsys):
    from core.app import JarvisApp
    from core.runtime_state import RuntimeState
    from ui.tray_app import JarvisTrayApp

    runtime = RuntimeState(wake_word_enabled=True)
    app = JarvisApp(speak_enabled=False, runtime=runtime)
    tray = JarvisTrayApp(app, start_wakeword_thread=True)

    mock_icon = MagicMock()
    fake_pystray = MagicMock()
    fake_pystray.Icon.return_value = mock_icon
    with (
        patch.dict(sys.modules, {"pystray": fake_pystray}),
        patch("ui.tray_app._create_icon_image"),
        patch(
            "voice.wakeword_loop.start_wakeword_loop",
            side_effect=RuntimeError("oww missing"),
        ),
        patch("services.watchdog.WatchdogService") as wdog,
    ):
        wdog.return_value.start.return_value = None
        wdog.return_value.run_once.return_value = None

        def end_run():
            runtime.stop()
            app._running = False

        mock_icon.run = MagicMock(side_effect=end_run)
        tray.start()

    out = capsys.readouterr().out
    assert "Wake word failed" in out
    assert "Tray started" in out
    mock_icon.run.assert_called_once()


def test_main_smoke_flag_exits(capsys):
    with patch("core.startup.run_smoke_test", return_value=0) as smoke:
        with patch.object(sys, "argv", ["main.py", "--smoke"]):
            import main

            assert main.main() == 0
    smoke.assert_called_once()


def test_main_tray_prints_diagnostics(capsys):
    argv = ["main.py", "--tray", "--debug-startup"]
    with (
        patch.object(sys, "argv", argv),
        patch("core.startup.probe_optional_imports", return_value={}),
        patch("core.startup.is_windows_store_python_stub", return_value=False),
        patch("ui.tray_app.JarvisTrayApp") as TrayCls,
        patch("core.app.JarvisApp") as AppCls,
        patch("core.startup.check_env_file", return_value=True),
    ):
        AppCls.return_value.speak_enabled = False
        AppCls.return_value.runtime.wake_word_enabled = False
        AppCls.return_value.runtime.voice_enabled = False
        TrayCls.return_value.start.return_value = None
        import main

        main.main()

    out = capsys.readouterr().out
    assert "JARVIS STARTUP" in out
    assert "Mode:" in out
    assert "Loaded .env:" in out
    assert "Python executable:" in out
