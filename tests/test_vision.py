"""Vision / screen understanding tests (mocked APIs)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.vision_actions import (
    DescribeScreenAction,
    DetectScreenErrorsAction,
    ReadScreenTextAction,
    TakeScreenshotAction,
)
from brain.intent_classifier import classify_rules
from config import (
    CONFIRMATION_REQUIRED_INTENTS,
    SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
    VISION_CAPTURE_DIR,
    VISION_DISABLED_MESSAGE,
)
from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, CommandRequest, Intent
from ui.tray_app import TRAY_MENU_COMMANDS, JarvisTrayApp
from vision.ocr import OCRResult, extract_text
from vision.redaction import redact_sensitive_text
from vision.screen_analyzer import describe_screen, detect_screen_errors, read_screen_text
from vision.screen_capture import ScreenshotResult, VisionDisabledError, capture_screen
from vision.window_info import WindowInfo


def _fake_image():
    img = MagicMock()
    img.width = 1920
    img.height = 1080
    img.save = MagicMock()
    return img


@pytest.fixture
def enabled_vision(monkeypatch, tmp_path):
    cap = tmp_path / "screenshots"
    monkeypatch.setattr("config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("actions.vision_actions.config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("config.VISION_ENABLED", True)
    monkeypatch.setattr("config.VISION_CAPTURE_DIR", cap)
    monkeypatch.setattr("config.VISION_SAVE_SCREENSHOTS", False)
    monkeypatch.setattr("vision.screen_capture.VISION_ENABLED", True)
    monkeypatch.setattr("vision.screen_capture.VISION_CAPTURE_DIR", cap)
    monkeypatch.setattr("vision.screen_capture.VISION_SAVE_SCREENSHOTS", False)
    return cap


def test_vision_disabled_returns_blocked(monkeypatch):
    monkeypatch.setattr("config.VISION_ENABLED", False)
    monkeypatch.setattr("config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("actions.vision_actions.config.VISION_ENABLED", False)
    monkeypatch.setattr("actions.vision_actions.config.SCREEN_UNDERSTANDING_ENABLED", False)
    monkeypatch.setattr("vision.screen_capture.VISION_ENABLED", False)
    action = DescribeScreenAction()
    result = action.execute(
        CommandRequest(raw_text="describe screen", intent=Intent.DESCRIBE_SCREEN)
    )
    assert result.status == ActionStatus.BLOCKED
    assert (
        SCREEN_UNDERSTANDING_DISABLED_MESSAGE in result.summary
        or VISION_DISABLED_MESSAGE in result.summary
    )


def test_capture_raises_when_disabled(monkeypatch):
    monkeypatch.setattr("vision.screen_capture.VISION_ENABLED", False)
    with pytest.raises(VisionDisabledError):
        capture_screen()


def test_capture_path_under_capture_dir(enabled_vision, monkeypatch):
    monkeypatch.setattr("vision.screen_capture.VISION_SAVE_SCREENSHOTS", True)
    monkeypatch.setattr("config.VISION_SAVE_SCREENSHOTS", True)
    img = _fake_image()
    with patch("vision.screen_capture._grab_monitor", return_value=(img, {"width": 100, "height": 50})):
        shot = capture_screen(save=True)
    assert shot.saved_path is not None
    base = enabled_vision.resolve()
    assert str(shot.saved_path).startswith(str(base))


def test_ocr_missing_tesseract_graceful(monkeypatch):
    monkeypatch.setattr("vision.ocr._tesseract_available", lambda: False)
    result = extract_text(_fake_image())
    assert result.error
    assert "Tesseract" in result.error


def test_redaction_removes_secrets():
    raw = "api_key=secret123 password=abc Bearer sk-abcdefghijklmnop0123456789"
    out = redact_sensitive_text(raw)
    assert "secret123" not in out
    assert "abc" not in out or "[redacted]" in out
    assert "sk-" not in out


def test_detect_screen_errors_english_and_hebrew(enabled_vision, monkeypatch):
    ocr = OCRResult(
        lines=[
            "All good",
            "Error: connection failed",
            "שגיאה: אין גישה",
        ]
    )
    with patch("vision.screen_analyzer._ocr_from_capture", return_value=(ocr, None, {})):
        data = detect_screen_errors()
    assert data["match_count"] >= 2
    patterns = {m["pattern"] for m in data["matches"]}
    assert "error" in patterns or "שגיאה" in patterns


def test_describe_screen_includes_window_and_ocr(enabled_vision, monkeypatch):
    active = WindowInfo(title="Cursor", width=800, height=600)
    ocr = OCRResult(lines=["Dashboard health OK", "CPU 12%"])
    with (
        patch("vision.screen_analyzer.get_active_window_info", return_value=active),
        patch("vision.screen_analyzer.list_visible_windows", return_value=[active]),
        patch("vision.screen_analyzer._ocr_from_capture", return_value=(ocr, None, {"width": 800, "height": 600})),
    ):
        data = describe_screen()
    assert "Cursor" in data["summary"]
    assert data["likely_app"]
    assert data["ocr_lines"]


def test_take_screenshot_not_saved_by_default(enabled_vision, monkeypatch):
    img = _fake_image()
    shot = ScreenshotResult(
        image=img,
        width=100,
        height=50,
        monitor={},
        saved_path=None,
        temp_path=Path("/tmp/x.png"),
    )
    with (
        patch("vision.screen_analyzer.capture_screen", return_value=shot),
        patch("vision.screen_analyzer.cleanup_temp"),
    ):
        from vision.screen_analyzer import take_screenshot_data

        data = take_screenshot_data(save=False)
    assert data["saved"] is False
    assert data["path"] is None
    assert "Not saved" in data["summary"] or "memory" in data["summary"].lower()


def test_read_screen_text_caps_and_redacts(enabled_vision, monkeypatch):
    monkeypatch.setattr("config.VISION_MAX_OCR_CHARS", 100)
    monkeypatch.setattr("vision.screen_analyzer.VISION_MAX_OCR_CHARS", 100)
    long_text = "line\n" * 200 + "token=abc123"
    ocr = OCRResult(text=long_text, lines=long_text.splitlines())
    with patch("vision.screen_analyzer._ocr_from_capture", return_value=(ocr, None, {})):
        data = read_screen_text()
    assert len(data["text"]) <= 100
    assert "abc123" not in data["text"]


def test_vision_actions_return_structured_result(enabled_vision, monkeypatch):
    with patch(
        "actions.vision_actions.describe_screen",
        return_value={"summary": "Screen OK", "likely_app": "Cursor"},
    ):
        result = DescribeScreenAction().execute(
            CommandRequest(raw_text="x", intent=Intent.DESCRIBE_SCREEN)
        )
    assert result.status == ActionStatus.SUCCESS
    assert result.data.get("likely_app") == "Cursor"


def test_tray_vision_menu_safe_and_uses_handle_text_command():
    for key in ("describe_screen", "detect_screen_errors"):
        cmd = TRAY_MENU_COMMANDS[key]
        req = classify_rules(cmd)
        assert req.intent.value not in CONFIRMATION_REQUIRED_INTENTS

    app = JarvisApp(speak_enabled=False, runtime=RuntimeState())
    tray = JarvisTrayApp(app)
    with (
        patch.object(app, "handle_text_command") as handle,
        patch("ui.tray_app.notify"),
    ):
        handle.return_value = MagicMock(
            intent=Intent.DESCRIBE_SCREEN,
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
        )
        tray._run_command(TRAY_MENU_COMMANDS["describe_screen"])
    handle.assert_called_once_with("describe screen", input_mode="text", print_result=False)


def test_no_mouse_keyboard_control_apis_in_vision_package():
    modules = (
        "vision/screen_capture.py",
        "vision/screen_analyzer.py",
        "vision/window_info.py",
        "vision/ocr.py",
        "actions/vision_actions.py",
    )
    root = Path(__file__).resolve().parent.parent
    forbidden = ("pyautogui", "pynput", "send_keys", "mouse.click", "keyboard.press")
    for rel in modules:
        source = (root / rel).read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in source, f"{token} found in {rel}"


def test_hebrew_intent_mappings():
    cases = [
        ("מה יש במסך", Intent.DESCRIBE_SCREEN),
        ("קרא את הטקסט במסך", Intent.READ_SCREEN_TEXT),
        ("יש שגיאה במסך", Intent.DETECT_SCREEN_ERRORS),
        ("איזה חלון פתוח", Intent.GET_ACTIVE_WINDOW),
        ("צלם מסך", Intent.TAKE_SCREENSHOT),
        ("תראה חלונות פתוחים", Intent.LIST_VISIBLE_WINDOWS),
    ]
    for text, expected in cases:
        req = classify_rules(text)
        assert req.intent == expected, text
