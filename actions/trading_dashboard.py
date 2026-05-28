"""Trading dashboard actions."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import urlparse

from actions.base import BaseAction
from actions.powershell import run_allowlisted_script
from config import (
    ALLOWED_TRADING_DASHBOARD_URL,
    DASHBOARD_HEALTH_URL,
    DASHBOARD_SUMMARY_URL,
    TRADING_DASHBOARD_SCRIPT,
    TRADING_DASHBOARD_URL,
)
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent

_HEALTH_WAIT_TIMEOUT_SEC = 8.0
_HEALTH_POLL_INTERVAL_SEC = 0.5


def resolve_trading_dashboard_url(raw: str | None = None) -> str:
    """Return the only allowlisted dashboard URL (localhost:8077). Rejects arbitrary URLs."""
    from config import _resolve_trading_dashboard_url

    candidate = raw if raw is not None else TRADING_DASHBOARD_URL
    return _resolve_trading_dashboard_url(candidate)


def dashboard_health_reachable() -> bool:
    return _fetch_json(DASHBOARD_HEALTH_URL) is not None


def wait_for_dashboard_health(
    timeout_sec: float = _HEALTH_WAIT_TIMEOUT_SEC,
    interval_sec: float = _HEALTH_POLL_INTERVAL_SEC,
) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if dashboard_health_reachable():
            return True
        time.sleep(interval_sec)
    return dashboard_health_reachable()


def open_trading_dashboard_in_browser() -> bool:
    """Open the fixed allowlisted dashboard URL in the default browser."""
    url = resolve_trading_dashboard_url(TRADING_DASHBOARD_URL)
    try:
        return bool(webbrowser.open(url, new=2))
    except OSError:
        return False


def _fetch_json(url: str, timeout: float = 2.0) -> dict | None:
    if not _is_allowlisted_http_url(url):
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
        return None


def _is_allowlisted_http_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "http"
        and host in ("127.0.0.1", "localhost")
        and parsed.port == 8077
    )


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _open_dashboard_full(request: CommandRequest) -> CommandResult:
    """Start dashboard if needed, then open allowlisted URL in browser."""
    url = resolve_trading_dashboard_url(TRADING_DASHBOARD_URL)
    was_healthy = dashboard_health_reachable()
    script_msg: str | None = None
    script_error: str | None = None

    if not was_healthy:
        try:
            script_msg = run_allowlisted_script(TRADING_DASHBOARD_SCRIPT)
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            script_error = str(exc)
        wait_for_dashboard_health()

    healthy_after = dashboard_health_reachable()
    browser_ok = open_trading_dashboard_in_browser()

    if browser_ok and healthy_after:
        summary = f"Trading dashboard opened at {url}"
        if script_msg and not was_healthy:
            summary = f"{summary}\n{script_msg}"
        return result_success(
            Intent.OPEN_TRADING_DASHBOARD,
            summary,
            data={"url": url, "server_healthy": True, "browser_opened": True},
        )

    if browser_ok and not healthy_after:
        parts = [
            f"Opened {url} in your browser, but the dashboard server is not responding on the health endpoint.",
        ]
        if script_error:
            parts.append(f"Could not start dashboard script: {script_error}")
        elif script_msg:
            parts.append(script_msg)
        summary = " ".join(parts)
        return result_success(
            Intent.OPEN_TRADING_DASHBOARD,
            summary,
            data={"url": url, "server_healthy": False, "browser_opened": True},
            next_suggestions=["show dashboard health", "run diagnostics"],
        )

    if script_error and not browser_ok:
        return result_failed(
            Intent.OPEN_TRADING_DASHBOARD,
            f"Could not start dashboard ({script_error}) and could not open the browser.",
            error=script_error,
        )

    return result_failed(
        Intent.OPEN_TRADING_DASHBOARD,
        f"Could not open the trading dashboard in your browser ({url}).",
        error="webbrowser.open failed",
        next_suggestions=["show dashboard health"],
    )


class OpenTradingDashboardAction(BaseAction):
    intent = Intent.OPEN_TRADING_DASHBOARD.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _open_dashboard_full(request)


class OpenTradingDashboardUrlAction(BaseAction):
    intent = Intent.OPEN_TRADING_DASHBOARD_URL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        url = resolve_trading_dashboard_url(TRADING_DASHBOARD_URL)
        if open_trading_dashboard_in_browser():
            return result_success(
                Intent.OPEN_TRADING_DASHBOARD_URL,
                f"Opened trading dashboard URL in browser: {url}",
                data={"url": url},
            )
        return result_failed(
            Intent.OPEN_TRADING_DASHBOARD_URL,
            f"Could not open the trading dashboard URL in your browser ({url}).",
            error="webbrowser.open failed",
        )


class ShowDashboardHealthAction(BaseAction):
    intent = Intent.SHOW_DASHBOARD_HEALTH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        port_up = _port_open("127.0.0.1", 8077)
        health = _fetch_json(DASHBOARD_HEALTH_URL)
        summary_data = _fetch_json(DASHBOARD_SUMMARY_URL)

        reachable = health is not None or port_up
        lines = [f"Dashboard reachable: {'yes' if reachable else 'no'}"]

        if health:
            status = health.get("status") or health.get("state") or "ok"
            lines.append(f"Health status: {status}")
            for key in ("kill_switch", "killSwitch", "execution_mode", "mode"):
                if key in health:
                    lines.append(f"{key}: {health[key]}")
        elif not reachable:
            lines.append("Health endpoint unavailable (dashboard may be off).")
        else:
            lines.append("Port 8077 open but /api/health returned no JSON.")

        if summary_data:
            lines.append("Dashboard summary:")
            for key in (
                "kill_switch",
                "execution_mode",
                "latest_run",
                "run_summary",
                "errors",
            ):
                if key in summary_data:
                    lines.append(f"  {key}: {summary_data[key]}")

        data = {
            "reachable": reachable,
            "port_open": port_up,
            "health": health,
            "summary": summary_data,
        }
        if not reachable:
            return result_failed(
                Intent.SHOW_DASHBOARD_HEALTH,
                "\n".join(lines),
                data=data,
            )
        return result_success(
            Intent.SHOW_DASHBOARD_HEALTH,
            "\n".join(lines),
            data=data,
        )
