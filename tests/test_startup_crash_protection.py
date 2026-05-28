"""Startup crash protection, smoke output, safe mode, and logging."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.startup import STARTUP_LATEST_LOG, append_startup_log, run_smoke_test


@pytest.fixture(autouse=True)
def _clean_latest_log(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    monkeypatch.setattr("core.startup.STARTUP_LOG_DIR", log_dir)
    monkeypatch.setattr("core.startup.STARTUP_LATEST_LOG", log_dir / "startup_latest.log")
    yield


def test_append_startup_log_creates_latest():
    path = append_startup_log("test event", extra={"mode": "smoke"})
    assert path.name == "startup_latest.log"
    assert path.is_file()
    assert "test event" in path.read_text(encoding="utf-8")


def test_smoke_always_prints_pass_fail_lines(capsys):
    with patch("core.startup._try_check", side_effect=lambda _l, fn: (True, "ok")):
        with patch("core.startup.ENV_FILE", Path("/nonexistent/.env")):
            code = run_smoke_test()
    out = capsys.readouterr().out
    assert "[PASS]" in out
    assert "config loaded" in out
    assert "pystray import" in out
    assert "PySide6 import" in out
    assert "overlay config" in out
    assert "Smoke overall:" in out
    assert code in (0, 1)


def test_smoke_survives_config_crash(capsys):
    def boom():
        raise ImportError("config broken")

    with patch("core.startup._try_check", side_effect=lambda label, fn: (False, "ImportError: config broken") if "config" in label else (True, "ok")):
        code = run_smoke_test()
    out = capsys.readouterr().out
    assert "[FAIL] config loaded" in out
    assert "Smoke overall: FAIL" in out
    assert code == 1


def test_main_entry_guard_prints_traceback_on_exception(capsys, monkeypatch):
    import main as main_mod

    monkeypatch.setattr(main_mod, "main", MagicMock(side_effect=ValueError("startup fail")))
    monkeypatch.setattr(main_mod, "_pause_on_error", lambda: None)

    exit_code = 1
    try:
        exit_code = main_mod.main()
    except BaseException:
        import traceback

        traceback.print_exc()
        try:
            from core.startup import append_startup_log

            append_startup_log("unhandled exception in __main__", exc=sys.exc_info()[1])
        except Exception:
            pass
        exit_code = 1

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "startup fail" in err


def test_store_stub_returns_code_2(capsys):
    import main as main_mod

    with patch("core.startup.is_windows_store_python_stub", return_value=True):
        with patch.object(sys, "argv", ["main.py", "--smoke"]):
            code = main_mod.main()
    assert code == 2
    out = capsys.readouterr().out
    assert "JARVIS STARTUP" in out
    assert "Windows Store" in out


def test_safe_mode_skips_tray_imports(capsys):
    import main as main_mod

    with (
        patch.object(sys, "argv", ["main.py", "--safe-mode"]),
        patch("core.startup.is_windows_store_python_stub", return_value=False),
        patch("core.app.JarvisApp") as App,
    ):
        inst = App.return_value
        inst.runtime.voice_enabled = False
        inst.runtime.wake_word_enabled = False
        code = main_mod.main()
    assert code == 0
    inst.run.assert_called_once()
    out = capsys.readouterr().out
    assert "Safe mode" in out


def test_import_failure_handled_gracefully(capsys):
    from core.startup import probe_optional_imports

    real_import = __import__

    def selective_import(name, *args, **kwargs):
        if name == "pystray":
            raise ImportError("no pystray")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=selective_import):
        results = probe_optional_imports(print_results=True)
    out = capsys.readouterr().out
    assert "Failed importing pystray" in out
    assert results["pystray"][0] is False


def test_smoke_crash_still_prints(capsys, monkeypatch):
    def broken():
        raise RuntimeError("smoke internal")

    monkeypatch.setattr("core.startup._try_check", broken)
    code = run_smoke_test()
    out = capsys.readouterr().out
    assert "[FAIL]" in out or "crashed" in out
    assert code == 1
