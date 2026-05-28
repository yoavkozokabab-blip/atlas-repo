"""Session state persistence tests."""

import json
from pathlib import Path

import pytest

from core.session import SessionState


def test_session_save_and_load(tmp_path: Path, monkeypatch):
    path = tmp_path / "session_state.json"
    monkeypatch.setattr("config.SESSION_STATE_PATH", path)

    state = SessionState.load()
    state.last_command_text = "open cursor"
    state.last_intent = "open_cursor"
    state.save()

    loaded = SessionState.load()
    assert loaded.last_command_text == "open cursor"
    assert loaded.last_intent == "open_cursor"


def test_corrupt_session_does_not_crash(tmp_path: Path, monkeypatch):
    path = tmp_path / "session_state.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr("config.SESSION_STATE_PATH", path)

    state = SessionState.load()
    assert state.current_project_root


def test_safe_path_rejects_outside_project(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "config.TRADING_PROJECT_ROOT",
        tmp_path / "project",
    )
    state = SessionState(current_project_root=str(tmp_path / "project"))
    state.last_opened_log = "C:\\Windows\\system.ini"
    assert state.safe_path("last_opened_log") is None
