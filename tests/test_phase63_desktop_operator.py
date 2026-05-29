"""Tests for Phase 63 desktop operator runtime."""

from __future__ import annotations

import os
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent
from desktop.control_runtime import (
    _needs_approval,
    extract_button_label,
    extract_type_text,
)


def test_intent_classification_phase63():
    assert classify_rules("what is on my screen").intent == Intent.WHAT_IS_ON_MY_SCREEN
    assert classify_rules("summarize this screen").intent == Intent.SUMMARIZE_THIS_SCREEN
    assert classify_rules("click the button that says OK").intent == Intent.CLICK_BUTTON_THAT_SAYS
    assert classify_rules("type this hello").intent == Intent.TYPE_THIS
    assert classify_rules("switch to chrome").intent == Intent.SWITCH_TO_CHROME
    assert classify_rules("list open windows").intent == Intent.LIST_OPEN_WINDOWS


def test_extractors():
    assert extract_button_label("click the button that says Save") == "Save"
    assert extract_type_text("type this jarvis test") == "jarvis test"


def test_safety_gates():
    assert _needs_approval("click_button", "delete account") is True
    assert _needs_approval("type_text", "hello world") is False


def test_actions_registered():
    from actions.registry import ActionRegistry

    reg = ActionRegistry()
    for intent in (
        Intent.WHAT_IS_ON_MY_SCREEN,
        Intent.SUMMARIZE_THIS_SCREEN,
        Intent.CLICK_BUTTON_THAT_SAYS,
        Intent.TYPE_THIS,
        Intent.SWITCH_TO_CHROME,
        Intent.LIST_OPEN_WINDOWS,
    ):
        assert reg.has(intent.value)


@patch("desktop.vision_runtime.what_is_on_my_screen", return_value="REAL DESKTOP VISION\nok")
def test_what_is_on_my_screen_action(_mock):
    from actions.phase63_desktop_actions import WhatIsOnMyScreenAction

    result = WhatIsOnMyScreenAction().execute(
        CommandRequest(raw_text="what is on my screen", intent=Intent.WHAT_IS_ON_MY_SCREEN)
    )
    assert "REAL DESKTOP VISION" in result.summary


def test_desktop_screenshot_cleanup_keeps_newest(monkeypatch, tmp_path):
    import desktop.vision_runtime as runtime

    class FakeImage:
        def save(self, path, format=None):
            path.write_bytes(b"new")

    base = time.time() - 100.0
    for idx in range(12):
        path = tmp_path / f"old_{idx}.png"
        path.write_bytes(b"old")
        os.utime(path, (base + idx, base + idx))

    monkeypatch.setattr(runtime, "SCREEN_UNDERSTANDING_ENABLED", True)
    monkeypatch.setattr(runtime, "_SCREENSHOT_DIR", tmp_path)
    monkeypatch.setattr(runtime, "add_ui_transition", lambda *_args, **_kwargs: None)
    removed: list[str] = []
    monkeypatch.setattr(
        runtime,
        "remove_file_best_effort",
        lambda path, **_kwargs: removed.append(path.name) or True,
    )

    capture = SimpleNamespace(ok=True, image=FakeImage(), error=None, warning=None)
    with patch("vision.screen_capture.safe_capture_screen", return_value=capture):
        ok, saved_path, _msg = runtime.capture_active_monitor()

    assert ok is True
    assert saved_path
    assert os.path.exists(saved_path)
    assert removed == ["old_2.png", "old_1.png", "old_0.png"]
