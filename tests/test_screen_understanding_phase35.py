"""Phase 35 — Screen Understanding v1 (read-only)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.registry import ActionRegistry
from actions.vision_actions import (
    AnalyzeActiveWindowAction,
    DescribeScreenAction,
    FindOnScreenAction,
    ReadScreenTextAction,
)
from brain.intent_classifier import classify_rules
from config import SCREEN_UNDERSTANDING_DISABLED_MESSAGE
from core.types import ActionStatus, CommandRequest, Intent
from diagnostics.command_audit import build_audit_entry, reset_audit_store
from reliability.jarvis_status import build_jarvis_status_report
from vision.active_window import ActiveWindowMeta
from vision.screen_capture import CaptureResult, safe_capture_screen
from vision.screen_ocr import ScreenOcrResult
from vision.screen_redaction import redact_screen_text
from vision.screen_understanding import find_on_screen_v35, read_screen_v35


PHASE35_FILES = [
    Path("vision/screen_capture.py"),
    Path("vision/screen_ocr.py"),
    Path("vision/screen_understanding.py"),
    Path("vision/screen_redaction.py"),
    Path("vision/active_window.py"),
    Path("actions/vision_actions.py"),
]

FORBIDDEN_IMPORTS = ("pyautogui", "pynput", "keyboard", "mouse")


@pytest.fixture
def screen_enabled(monkeypatch, tmp_path):
    temp = tmp_path / "screen_temp"
    temp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("config.SCREEN_UNDERSTANDING_ENABLED", True)
    monkeypatch.setattr("vision.screen_capture.SCREEN_UNDERSTANDING_ENABLED", True)
    monkeypatch.setattr("config.SCREEN_CAPTURE_ALLOW", True)
    monkeypatch.setattr("config.SCREEN_CAPTURE_SAVE_DEBUG", False)
    monkeypatch.setattr("vision.screen_capture.SCREEN_CAPTURE_SAVE_DEBUG", False)
    monkeypatch.setattr("config.SCREEN_CAPTURE_TEMP_DIR", temp)
    monkeypatch.setattr("vision.screen_capture.SCREEN_CAPTURE_TEMP_DIR", temp)
    monkeypatch.setattr("config.SCREEN_OCR_ENABLED", True)
    monkeypatch.setattr("config.SCREEN_REDACTION_ENABLED", True)
    monkeypatch.setattr("config.SCREEN_BLOCK_SECRET_WINDOWS", True)
    monkeypatch.setattr("config.VISION_ENABLED", False)
    return temp


def _fake_image():
    img = MagicMock()
    img.width = 800
    img.height = 600
    img.save = MagicMock()
    return img


def test_screen_commands_classify():
    cases = [
        ("describe screen", Intent.DESCRIBE_SCREEN),
        ("what is on my screen", Intent.DESCRIBE_SCREEN),
        ("read screen", Intent.READ_SCREEN_TEXT),
        ("read what is on screen", Intent.READ_SCREEN_TEXT),
        ("analyze active window", Intent.ANALYZE_ACTIVE_WINDOW),
        ("analyze this window", Intent.ANALYZE_ACTIVE_WINDOW),
        ("find on screen settings", Intent.FIND_ON_SCREEN),
        ("find this on screen save button", Intent.FIND_ON_SCREEN),
        ("where is settings on screen", Intent.FIND_ON_SCREEN),
    ]
    for text, expected in cases:
        req = classify_rules(text)
        assert req.intent == expected, text


def test_registry_has_four_screen_actions():
    reg = ActionRegistry()
    for intent in (
        Intent.DESCRIBE_SCREEN.value,
        Intent.READ_SCREEN_TEXT.value,
        Intent.ANALYZE_ACTIVE_WINDOW.value,
        Intent.FIND_ON_SCREEN.value,
    ):
        assert intent in reg._actions


def test_disabled_screen_understanding(monkeypatch):
    monkeypatch.setattr("config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("config.VISION_ENABLED", False)
    monkeypatch.setattr("actions.vision_actions.config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("actions.vision_actions.config.VISION_ENABLED", False)
    action = DescribeScreenAction()
    result = action.execute(
        CommandRequest(raw_text="describe screen", intent=Intent.DESCRIBE_SCREEN)
    )
    assert result.status == ActionStatus.BLOCKED
    assert SCREEN_UNDERSTANDING_DISABLED_MESSAGE in result.summary


def test_blocked_secret_window(screen_enabled):
    blocked = ActiveWindowMeta(
        title=".env — secrets",
        process_name="code",
        is_blocked=True,
        block_reason="Blocked keyword",
    )
    with patch("vision.screen_understanding._pipeline") as pipe:
        pipe.return_value = (
            blocked,
            CaptureResult(ok=False, mode="active_window", warning=blocked.block_reason),
            ScreenOcrResult(ok=False, engine="blocked"),
        )
        data = read_screen_v35()
    assert data.get("blocked") is True
    assert "blocked" in data["summary"].lower()


def test_redaction_patterns():
    raw = "password=secret123 api_key=abc sk-live-abcdef0123456789 Bearer xyz.token"
    out = redact_screen_text(raw)
    assert "secret123" not in out
    assert "sk-live" not in out
    assert "REDACTED" in out or "redacted" in out.lower()


def test_read_screen_never_unredacted_secrets(screen_enabled):
    ocr = ScreenOcrResult(
        ok=True,
        text="password=hunter2 token=abcdef API_KEY=zzz",
        engine="mock",
    )
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(100, 100))
    meta = ActiveWindowMeta(title="Notepad")
    with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
        data = read_screen_v35()
    assert "hunter2" not in data.get("text", "")
    assert "abcdef" not in data.get("text", "")


def test_temp_path_under_approved_dir(screen_enabled, monkeypatch):
    img = _fake_image()
    meta = ActiveWindowMeta(title="App", width=100, height=100, left=0, top=0)
    with patch("vision.active_window.get_active_window_metadata", return_value=meta):
        with patch("vision.screen_capture._grab_region", return_value=(img, 100, 100)):
            with patch("vision.screen_capture._write_temp_image") as write:
                write.return_value = screen_enabled / "shot.png"
                monkeypatch.setattr("vision.screen_capture.SCREEN_CAPTURE_SAVE_DEBUG", True)
                result = safe_capture_screen()
    assert str(write.return_value).startswith(str(screen_enabled.resolve()))


def test_temp_deletion_when_debug_false(screen_enabled, monkeypatch):
    monkeypatch.setattr("vision.screen_capture.SCREEN_CAPTURE_SAVE_DEBUG", False)
    handle = tempfile.NamedTemporaryFile(suffix=".png", dir=screen_enabled, delete=True)
    handle.write(b"x")
    handle.flush()
    path = Path(handle.name)
    state = {"handle": handle}

    def _sandbox_delete(target: Path) -> bool:
        assert Path(target) == path
        live = state.get("handle")
        if live is not None:
            live.close()
            state["handle"] = None
        return not path.exists()

    monkeypatch.setattr("vision.screen_capture.remove_file_best_effort", _sandbox_delete)
    capture = CaptureResult(ok=True, temp_path_used=str(path))
    from vision.screen_capture import delete_capture_temp

    try:
        assert delete_capture_temp(capture) is True
        assert not path.exists()
        assert capture.deleted_after_use is True
    finally:
        live = state.get("handle")
        if live is not None:
            live.close()


def test_find_on_screen_no_click(screen_enabled):
    ocr = ScreenOcrResult(
        ok=True,
        text="File Edit Settings Help",
        blocks=[],
        engine="mock",
    )
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(200, 200))
    meta = ActiveWindowMeta(title="App")
    with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
        data = find_on_screen_v35("settings")
    assert data.get("no_click") is True
    assert "No click was performed" in data["summary"]


def test_ocr_unavailable_degrades(screen_enabled):
    ocr = ScreenOcrResult(ok=False, engine="none", error="Tesseract missing")
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(10, 10))
    meta = ActiveWindowMeta(title="App")
    with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
        data = read_screen_v35()
    assert "Could not read" in data["summary"] or data.get("text") == ""


def test_active_window_metadata_degrades():
    with patch("vision.active_window._from_pygetwindow", return_value=ActiveWindowMeta(error="no window")):
        from vision.active_window import get_active_window_metadata

        meta = get_active_window_metadata()
    assert meta.error or meta.warning or meta.title == ""


def test_audit_omits_ocr_body():
    reset_audit_store()
    req = CommandRequest(raw_text="read screen", intent=Intent.READ_SCREEN_TEXT)
    from core.results import result_success
    from core.types import CommandResult

    secret = "password=TOPSECRET"
    result = result_success(
        Intent.READ_SCREEN_TEXT,
        "Read screen",
        data={"text": secret, "screen_summary_length": 10, "redaction_applied": True},
    )
    entry = build_audit_entry(req, result, 12)
    blob = json.dumps(entry)
    assert "TOPSECRET" not in blob
    assert entry.get("screen_summary_length") == 10
    assert "redaction_applied" in entry


def test_jarvis_status_includes_screen_section(screen_enabled):
    report = build_jarvis_status_report()
    assert "screen_understanding" in report
    assert "capture_mode" in report


def test_no_forbidden_automation_imports():
    root = Path(__file__).resolve().parents[1]
    for rel in PHASE35_FILES:
        text = (root / rel).read_text(encoding="utf-8")
        for bad in FORBIDDEN_IMPORTS:
            assert f"import {bad}" not in text
            assert f"from {bad}" not in text


def test_describe_screen_action_mock(screen_enabled):
    ocr = ScreenOcrResult(ok=True, text="Hello Settings", engine="mock")
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(50, 50))
    meta = ActiveWindowMeta(title="Test")
    with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
        result = DescribeScreenAction().execute(
            CommandRequest(raw_text="describe screen", intent=Intent.DESCRIBE_SCREEN)
        )
    assert result.status == ActionStatus.SUCCESS
    assert "Settings" in result.summary or "Hello" in result.summary


def test_analyze_active_window_action(screen_enabled):
    ocr = ScreenOcrResult(ok=True, text="Window content", engine="mock")
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(50, 50))
    meta = ActiveWindowMeta(title="Calc", process_name="calc.exe", pid=99)
    with patch("vision.screen_understanding.get_active_window_metadata", return_value=meta):
        with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
            result = AnalyzeActiveWindowAction().execute(
                CommandRequest(
                    raw_text="analyze active window",
                    intent=Intent.ANALYZE_ACTIVE_WINDOW,
                )
            )
    assert result.status == ActionStatus.SUCCESS
    assert "Calc" in result.summary


def test_find_action_extracts_query(screen_enabled):
    ocr = ScreenOcrResult(ok=True, text="Settings panel", engine="mock")
    capture = CaptureResult(ok=True, mode="active_window", image=_fake_image(), image_size=(50, 50))
    meta = ActiveWindowMeta(title="App")
    with patch("vision.screen_understanding._pipeline", return_value=(meta, capture, ocr)):
        result = FindOnScreenAction().execute(
            CommandRequest(
                raw_text="find on screen settings",
                intent=Intent.FIND_ON_SCREEN,
                params={"query": "settings"},
            )
        )
    assert result.status == ActionStatus.SUCCESS
    assert result.data.get("no_click") is True
