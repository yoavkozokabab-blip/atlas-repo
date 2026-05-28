"""Trading dashboard open action tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.trading_dashboard import (
    OpenTradingDashboardAction,
    OpenTradingDashboardUrlAction,
    dashboard_health_reachable,
    open_trading_dashboard_in_browser,
    resolve_trading_dashboard_url,
    wait_for_dashboard_health,
)
from brain.intent_classifier import classify_rules
from config import ALLOWED_TRADING_DASHBOARD_URL, TRADING_DASHBOARD_SCRIPT
from core.types import ActionStatus, Intent


def test_resolve_trading_dashboard_url_rejects_arbitrary():
    assert resolve_trading_dashboard_url("http://evil.com/dashboard") == (
        ALLOWED_TRADING_DASHBOARD_URL
    )
    assert resolve_trading_dashboard_url("http://127.0.0.1:9999") == (
        ALLOWED_TRADING_DASHBOARD_URL
    )
    assert resolve_trading_dashboard_url("http://127.0.0.1:8077") == (
        ALLOWED_TRADING_DASHBOARD_URL
    )


def test_classify_open_dashboard_phrases():
    for phrase in (
        "open dashboard",
        "open the dashboard",
        "show dashboard",
        "פתח דאשבורד",
        "פתח את הדאשבורד",
    ):
        req = classify_rules(phrase)
        assert req.intent == Intent.OPEN_TRADING_DASHBOARD, phrase


def test_classify_open_dashboard_url_phrases():
    for phrase in ("open dashboard url", "פתח כתובת דאשבורד"):
        req = classify_rules(phrase)
        assert req.intent == Intent.OPEN_TRADING_DASHBOARD_URL, phrase


@patch("actions.trading_dashboard.webbrowser.open", return_value=True)
@patch("actions.trading_dashboard.dashboard_health_reachable", return_value=True)
@patch("actions.trading_dashboard.run_allowlisted_script")
def test_open_dashboard_already_running(script, health, browser):
    result = OpenTradingDashboardAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD, raw_text="open dashboard")
    )
    script.assert_not_called()
    browser.assert_called_once_with(ALLOWED_TRADING_DASHBOARD_URL, new=2)
    assert result.status == ActionStatus.SUCCESS
    assert "Trading dashboard opened at http://127.0.0.1:8077" in result.summary


@patch("actions.trading_dashboard.webbrowser.open", return_value=True)
@patch("actions.trading_dashboard.wait_for_dashboard_health", return_value=True)
@patch("actions.trading_dashboard.dashboard_health_reachable", side_effect=[False, True])
@patch("actions.trading_dashboard.run_allowlisted_script", return_value="Started script")
def test_open_dashboard_starts_script_when_down(script, health, wait, browser):
    result = OpenTradingDashboardAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD, raw_text="open dashboard")
    )
    script.assert_called_once_with(TRADING_DASHBOARD_SCRIPT)
    wait.assert_called_once()
    browser.assert_called_once_with(ALLOWED_TRADING_DASHBOARD_URL, new=2)
    assert result.status == ActionStatus.SUCCESS
    assert "http://127.0.0.1:8077" in result.summary


@patch("actions.trading_dashboard.webbrowser.open", return_value=True)
@patch("actions.trading_dashboard.wait_for_dashboard_health", return_value=False)
@patch("actions.trading_dashboard.dashboard_health_reachable", return_value=False)
@patch("actions.trading_dashboard.run_allowlisted_script", return_value="Started script")
def test_open_dashboard_server_down_browser_opened(script, health, wait, browser):
    result = OpenTradingDashboardAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD, raw_text="open dashboard")
    )
    assert result.status == ActionStatus.SUCCESS
    assert "not responding" in result.summary.lower() or "Opened" in result.summary


@patch("actions.trading_dashboard.webbrowser.open", return_value=False)
@patch("actions.trading_dashboard.dashboard_health_reachable", return_value=True)
@patch("actions.trading_dashboard.run_allowlisted_script")
def test_open_dashboard_browser_failure(script, health, browser):
    result = OpenTradingDashboardAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD, raw_text="open dashboard")
    )
    assert result.status == ActionStatus.FAILED
    assert "browser" in result.summary.lower()


@patch("actions.trading_dashboard.webbrowser.open", return_value=True)
@patch("actions.trading_dashboard.run_allowlisted_script")
def test_open_dashboard_url_only_no_script(script, browser):
    result = OpenTradingDashboardUrlAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD_URL, raw_text="open dashboard url")
    )
    script.assert_not_called()
    browser.assert_called_once_with(ALLOWED_TRADING_DASHBOARD_URL, new=2)
    assert result.status == ActionStatus.SUCCESS
    assert "127.0.0.1:8077" in result.summary


@patch("actions.trading_dashboard.webbrowser.open", return_value=False)
def test_open_dashboard_url_browser_failure(browser):
    result = OpenTradingDashboardUrlAction().execute(
        MagicMock(intent=Intent.OPEN_TRADING_DASHBOARD_URL, raw_text="open dashboard url")
    )
    assert result.status == ActionStatus.FAILED


def test_run_allowlisted_script_rejects_non_allowlisted(tmp_path: Path):
    from actions.powershell import run_allowlisted_script

    evil = tmp_path / "evil.ps1"
    evil.write_text("Write-Host hi")
    with pytest.raises(ValueError, match="not allowlisted"):
        run_allowlisted_script(evil)


@patch("actions.trading_dashboard._fetch_json", return_value={"status": "ok"})
def test_dashboard_health_reachable(fetch):
    assert dashboard_health_reachable() is True


@patch("actions.trading_dashboard._fetch_json", return_value=None)
def test_wait_for_dashboard_health_retries(fetch):
    with patch("actions.trading_dashboard.time.sleep"):
        with patch(
            "actions.trading_dashboard.dashboard_health_reachable",
            side_effect=[False, True],
        ) as health:
            assert wait_for_dashboard_health(timeout_sec=1.0, interval_sec=0.01) is True
            assert health.call_count >= 2


@patch("actions.trading_dashboard.webbrowser.open", return_value=True)
def test_open_trading_dashboard_in_browser_uses_allowlisted_url(browser):
    assert open_trading_dashboard_in_browser() is True
    browser.assert_called_once_with(ALLOWED_TRADING_DASHBOARD_URL, new=2)


def test_router_open_dashboard_path():
    from brain.router import CommandRouter

    router = CommandRouter()
    with (
        patch("actions.trading_dashboard.dashboard_health_reachable", return_value=True),
        patch("actions.trading_dashboard.webbrowser.open", return_value=True),
        patch("actions.trading_dashboard.run_allowlisted_script") as script,
    ):
        result = router.route("open dashboard")
    script.assert_not_called()
    assert result.intent == Intent.OPEN_TRADING_DASHBOARD
    assert result.status == ActionStatus.SUCCESS
