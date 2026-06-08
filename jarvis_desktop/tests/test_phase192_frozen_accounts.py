"""Phase 192 — frozen accounts-service runner tests.

Verifies that the desktop launches the bundled AtlasAccounts.exe in frozen mode
(instead of `python -m accounts_service.main`) and points it at a writable data
directory.
"""
from __future__ import annotations

import os
import sys

import pytest

from jarvis_desktop import accounts_service_runner as runner


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(tmp_path))
    monkeypatch.delenv("ATLAS_ACCOUNTS_DB", raising=False)
    monkeypatch.delenv("ATLAS_ACCOUNTS_DATA_DIR", raising=False)
    runner._process = None
    yield
    runner._process = None


def test_service_env_points_at_writable_paths():
    env = runner._service_env()
    assert env.get("ATLAS_ACCOUNTS_DATA_DIR")
    assert os.path.isdir(env["ATLAS_ACCOUNTS_DATA_DIR"])
    assert env.get("ATLAS_ACCOUNTS_DB", "").startswith("sqlite:///")
    # The DB lives under the writable data dir, not the (possibly read-only) cwd.
    assert "accounts_service" in env["ATLAS_ACCOUNTS_DATA_DIR"]


def test_frozen_accounts_exe_found_next_to_atlas(monkeypatch, tmp_path):
    exe_dir = tmp_path / "app"
    (exe_dir / "accounts").mkdir(parents=True)
    fake = exe_dir / "accounts" / "AtlasAccounts.exe"
    fake.write_text("x")
    monkeypatch.setattr(sys, "executable", str(exe_dir / "Atlas.exe"))
    assert runner._frozen_accounts_exe() == str(fake)


def test_frozen_accounts_exe_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Atlas.exe"))
    assert runner._frozen_accounts_exe() is None


def test_frozen_start_spawns_bundled_exe(monkeypatch, tmp_path):
    # Arrange a fake frozen install with the bundled accounts exe.
    exe_dir = tmp_path / "app"
    (exe_dir / "accounts").mkdir(parents=True)
    fake = exe_dir / "accounts" / "AtlasAccounts.exe"
    fake.write_text("x")
    monkeypatch.setattr(runner, "_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "Atlas.exe"))
    monkeypatch.setattr(runner, "is_running", lambda: False)

    captured = {}

    class _FakeProc:
        pid = 4321
        def poll(self):
            return None

    def _fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        return _FakeProc()

    monkeypatch.setattr(runner.subprocess, "Popen", _fake_popen)

    ok = runner.start_accounts_service()
    assert ok is True
    assert captured["cmd"] == [str(fake)]            # spawns the exe, NOT python -m
    assert captured["env"]["ATLAS_ACCOUNTS_DB"].startswith("sqlite:///")
    assert captured["env"].get("ATLAS_ACCOUNTS_DATA_DIR")


def test_source_mode_uses_python_module(monkeypatch):
    monkeypatch.setattr(runner, "_frozen", lambda: False)
    monkeypatch.setattr(runner, "is_running", lambda: False)
    captured = {}

    class _FakeProc:
        pid = 1
        def poll(self):
            return None

    monkeypatch.setattr(runner.subprocess, "Popen", lambda cmd, **kw: (captured.update(cmd=cmd, env=kw.get("env")) or _FakeProc()))
    ok = runner.start_accounts_service()
    assert ok is True
    assert captured["cmd"][0] == sys.executable
    assert captured["cmd"][1:] == ["-m", "accounts_service.main"]
