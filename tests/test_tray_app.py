"""Tray app tests (mocked, no real Windows tray)."""

from unittest.mock import MagicMock, patch

import pytest

from brain.intent_classifier import classify_rules
from config import CONFIRMATION_REQUIRED_INTENTS
from core.app import JarvisApp
from core.runtime_state import RuntimeState
from core.types import ActionStatus, Intent
from ui.tray_app import TRAY_FORBIDDEN_INTENTS, TRAY_MENU_COMMANDS, JarvisTrayApp


@pytest.fixture
def app():
    runtime = RuntimeState(speak_enabled=False)
    return JarvisApp(speak_enabled=False, runtime=runtime)


def test_tray_menu_commands_are_safe_intents():
    for cmd in TRAY_MENU_COMMANDS.values():
        req = classify_rules(cmd)
        assert req.intent.value not in TRAY_FORBIDDEN_INTENTS
        assert req.intent.value not in CONFIRMATION_REQUIRED_INTENTS


def test_no_confirm_required_in_tray_menu_constants():
    assert "run_live_daily_loop" not in TRAY_MENU_COMMANDS
    assert "shutdown_jarvis" not in TRAY_MENU_COMMANDS


def test_menu_action_calls_handle_text_command(app):
    tray = JarvisTrayApp(app)
    with (
        patch.object(app, "handle_text_command") as handle,
        patch("ui.tray_app.notify") as notify,
    ):
        handle.return_value = MagicMock(
            intent=Intent.SHOW_DASHBOARD_HEALTH,
            status=ActionStatus.SUCCESS,
            summary="Dashboard OK",
            error=None,
        )
        tray._run_command("show dashboard health", title="Dashboard")
    handle.assert_called_once_with("show dashboard health", input_mode="text", print_result=False)
    notify.assert_called_once()


def test_dashboard_health_uses_router_path(app):
    tray = JarvisTrayApp(app)
    with (
        patch("ui.tray_app.notify"),
        patch("actions.trading_dashboard._fetch_json", return_value=None),
        patch("actions.trading_dashboard._port_open", return_value=False),
    ):
        result = app.handle_text_command(
            TRAY_MENU_COMMANDS["show_dashboard_health"],
            print_result=False,
        )
    assert result.intent == Intent.SHOW_DASHBOARD_HEALTH


def test_notification_failure_does_not_crash(app):
    tray = JarvisTrayApp(app)
    with patch.object(app, "handle_text_command") as handle:
        handle.return_value = MagicMock(
            intent=Intent.SHOW_CAPABILITIES,
            status=ActionStatus.SUCCESS,
            summary="ok",
            error=None,
        )
        with patch("ui.tray_app.notify", side_effect=RuntimeError("notify fail")):
            tray._run_command("show capabilities")


def test_tray_overlay_toggle(app):
    tray = JarvisTrayApp(app)
    with patch("ui.tray_app.notify"):
        tray._toggle_overlay()
    assert app.runtime.overlay_enabled is True
    with patch("ui.tray_app.notify"):
        tray._toggle_overlay()
    assert app.runtime.overlay_enabled is False


def test_tray_overlay_test_does_not_execute(app):
    tray = JarvisTrayApp(app)
    with patch.object(app, "handle_text_command") as handle:
        with patch("ui.tray_app.notify"):
            with patch("ui.overlay_app.time.sleep", return_value=None):
                tray._show_overlay_test()
    handle.assert_not_called()


def test_exit_calls_stop(app):
    tray = JarvisTrayApp(app)
    mock_icon = MagicMock()
    tray._icon = mock_icon
    with patch("ui.tray_app.notify"):
        tray._exit()
    assert app.runtime.running is False
    mock_icon.stop.assert_called_once()


def test_toggle_speak_updates_app(app):
    tray = JarvisTrayApp(app)
    with patch("ui.tray_app.notify"):
        tray._toggle_speak()
    assert app.runtime.speak_enabled is True
    assert app.speak_enabled is True
