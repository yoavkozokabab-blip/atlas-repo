"""Background quiet mode — config and overlay visibility."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from actions.overlay_quiet_actions import (
    HideOverlayAction,
    ShowOverlayAction,
    ToggleQuietModeAction,
)
from brain.intent_classifier import classify_rules
from core.types import CommandRequest, Intent
from ui.quiet_mode import (
    hide_overlay_window,
    init_quiet_mode_from_config,
    is_overlay_window_visible,
    is_quiet_mode,
    reset_quiet_mode_state,
    reveal_overlay_for_wake,
    set_quiet_mode,
    show_overlay_window,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_quiet_mode_state()
    yield
    reset_quiet_mode_state()


def test_config_flags_parse():
    import config as cfg

    assert isinstance(cfg.BACKGROUND_MODE, bool)
    assert isinstance(cfg.START_MINIMIZED, bool)
    assert isinstance(cfg.OVERLAY_START_HIDDEN, bool)
    assert isinstance(cfg.OVERLAY_SHOW_ON_WAKE, bool)


def test_overlay_hidden_when_background_start_hidden(monkeypatch):
    monkeypatch.setattr("ui.quiet_mode.BACKGROUND_MODE", True)
    monkeypatch.setattr("ui.quiet_mode.OVERLAY_START_HIDDEN", True)
    init_quiet_mode_from_config()
    assert is_quiet_mode()
    assert not is_overlay_window_visible()


def test_show_overlay_makes_visible():
    set_quiet_mode(True)
    hide_overlay_window()
    assert not is_overlay_window_visible()
    show_overlay_window()
    assert is_overlay_window_visible()


def test_reveal_on_wake_when_configured(monkeypatch):
    monkeypatch.setattr("ui.quiet_mode.OVERLAY_SHOW_ON_WAKE", True)
    set_quiet_mode(True)
    hide_overlay_window()
    reveal_overlay_for_wake()
    assert is_overlay_window_visible()


def test_classify_overlay_commands():
    assert classify_rules("show overlay").intent == Intent.SHOW_OVERLAY
    assert classify_rules("hide overlay").intent == Intent.HIDE_OVERLAY
    assert classify_rules("toggle quiet mode").intent == Intent.TOGGLE_QUIET_MODE


def test_show_overlay_action():
    set_quiet_mode(True)
    hide_overlay_window()
    r = ShowOverlayAction().execute(CommandRequest(raw_text="show overlay"))
    assert "shown" in r.summary.lower()
    assert is_overlay_window_visible()


def test_hide_overlay_action():
    show_overlay_window()
    r = HideOverlayAction().execute(CommandRequest(raw_text="hide overlay"))
    assert "hidden" in r.summary.lower()
    assert not is_overlay_window_visible()


def test_toggle_quiet_mode_action():
    set_quiet_mode(False)
    r = ToggleQuietModeAction().execute(CommandRequest(raw_text="toggle quiet mode"))
    assert "enabled" in r.summary.lower() or "on" in r.summary.lower()


def test_overlay_sync_respects_visibility_flag(monkeypatch):
    from ui.overlay_app import OverlayController, reset_overlay_controller
    from ui.overlay_state import OverlayState

    reset_overlay_controller()
    monkeypatch.setattr("ui.overlay_app.OVERLAY_QT_ENABLED", False)
    ctrl = OverlayController()
    ctrl.set_enabled(True)
    set_quiet_mode(True)
    hide_overlay_window()
    ctrl._state.set_wake_detected()
    snap = ctrl._state.snapshot()
    assert snap.visible is True
    assert not is_overlay_window_visible()
