"""Phase 16 safe website launcher tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from actions.website_actions import (
    ApproveWebsiteAction,
    ForgetWebsiteAction,
    OpenWebsiteAction,
)
from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from core import confirmation
from core.types import ActionStatus, CommandRequest, Intent
from ui.tray_app import TRAY_FORBIDDEN_INTENTS, TRAY_MENU_COMMANDS
from websites.launcher import launch_website
from websites.registry import ApprovedWebsite, WebsiteEntry, WebsiteRegistry
from websites.safety import SafetyError, validate_url


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "approved_websites.json"
    monkeypatch.setattr("websites.registry.APPROVED_WEBSITES_PATH", path)
    monkeypatch.setattr("config.APPROVED_WEBSITES_PATH", path)
    return WebsiteRegistry(path)


def test_open_builtin_website(registry):
    entry = WebsiteRegistry().resolve_for_open("youtube")
    assert entry is not None
    assert entry.builtin
    with patch("websites.launcher.webbrowser.open", return_value=True) as opener:
        msg = launch_website(entry)
    opener.assert_called_once()
    assert opener.call_args[0][0].startswith("https://")
    assert "Opened YouTube" in msg


def test_open_builtin_via_action(registry):
    with patch("websites.launcher.webbrowser.open", return_value=True):
        result = OpenWebsiteAction().execute(
            CommandRequest(
                raw_text="open chatgpt",
                intent=Intent.OPEN_WEBSITE,
                params={"website": "chatgpt"},
            )
        )
    assert result.status == ActionStatus.SUCCESS
    assert "ChatGPT" in result.summary


def test_blocked_scheme():
    with pytest.raises(SafetyError):
        validate_url("file:///etc/passwd")
    with pytest.raises(SafetyError):
        validate_url("javascript:alert(1)")
    with pytest.raises(SafetyError):
        validate_url("data:text/html,hi")


def test_blocked_localhost():
    with pytest.raises(SafetyError):
        validate_url("https://localhost/")
    with pytest.raises(SafetyError):
        validate_url("http://127.0.0.1:9999/")


def test_blocked_ip_url():
    with pytest.raises(SafetyError):
        validate_url("https://93.184.216.34/")


def test_blocked_suspicious_query():
    with pytest.raises(SafetyError):
        validate_url("https://example.com/?q=<script>alert(1)</script>")


def test_no_shell_subprocess():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "websites"
    forbidden = {"subprocess", "selenium", "playwright", "puppeteer"}
    for name in ("launcher.py", "registry.py", "safety.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "call" and isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "subprocess":
                        for kw in node.keywords:
                            if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
                                assert kw.value.value is not True


def test_uses_webbrowser_open_mock(registry):
    with patch("websites.launcher.webbrowser.open", return_value=True) as opener:
        OpenWebsiteAction().execute(
            CommandRequest(
                raw_text="open gmail",
                intent=Intent.OPEN_WEBSITE,
                params={"website": "gmail"},
            )
        )
    opener.assert_called_once()


def test_unknown_website_requires_confirmation(registry, monkeypatch):
    monkeypatch.setattr(
        "websites.registry._APPROVAL_CATALOG",
        {
            "testportal": {
                "display_name": "Test Portal",
                "url": "https://www.example.com",
            }
        },
    )
    req = CommandRequest(
        raw_text="open testportal",
        intent=Intent.OPEN_WEBSITE,
        params={"website": "testportal"},
    )
    result = OpenWebsiteAction().execute(req)
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert "Approve and open" in result.summary


def test_approve_custom_website(registry):
    result = ApproveWebsiteAction().execute(
        CommandRequest(
            raw_text="approve website mysite",
            intent=Intent.APPROVE_WEBSITE,
            params={
                "website": "mysite",
                "url": "https://docs.example.com",
                "display_name": "My Docs",
            },
        )
    )
    assert result.status == ActionStatus.SUCCESS
    approved = registry.get("mysite")
    assert approved is not None
    assert approved.url.startswith("https://")


def test_forget_website(registry):
    registry.approve(
        ApprovedWebsite(
            site_id="mysite",
            display_name="My Docs",
            url="https://docs.example.com",
        )
    )
    result = ForgetWebsiteAction().execute(
        CommandRequest(
            raw_text="forget website mysite",
            intent=Intent.FORGET_WEBSITE,
            params={"website": "mysite"},
        )
    )
    assert result.status == ActionStatus.SUCCESS
    assert registry.get("mysite") is None


def test_approval_persists(registry):
    registry.approve(
        ApprovedWebsite(
            site_id="mysite",
            display_name="My Docs",
            url="https://docs.example.com",
        )
    )
    data = json.loads(registry.path.read_text(encoding="utf-8"))
    assert "mysite" in data["websites"]


def test_confirmed_open_approves_and_launches(registry, monkeypatch):
    monkeypatch.setattr(
        "websites.registry._APPROVAL_CATALOG",
        {
            "testportal": {
                "display_name": "Test Portal",
                "url": "https://www.example.com",
            }
        },
    )
    with patch("websites.launcher.webbrowser.open", return_value=True):
        result = OpenWebsiteAction().execute(
            CommandRequest(
                raw_text="yes",
                intent=Intent.OPEN_WEBSITE,
                confirmed=True,
                params={
                    "site_id": "testportal",
                    "website_entry": {
                        "site_id": "testportal",
                        "display_name": "Test Portal",
                        "url": "https://www.example.com",
                    },
                },
            )
        )
    assert result.status == ActionStatus.SUCCESS
    assert registry.get("testportal") is not None


def test_multiple_matches_clarify(registry):
    result = OpenWebsiteAction().execute(
        CommandRequest(
            raw_text="open g",
            intent=Intent.OPEN_WEBSITE,
            params={"website": "g"},
        )
    )
    assert result.status == ActionStatus.CLARIFICATION_NEEDED


def test_router_open_website_path(registry):
    router = CommandRouter()
    with patch("websites.launcher.webbrowser.open", return_value=True):
        result = router.route("open youtube")
    assert result.intent == Intent.OPEN_WEBSITE
    assert result.status == ActionStatus.SUCCESS


def test_classify_open_chatgpt():
    req = classify_rules("open chatgpt")
    assert req.intent == Intent.OPEN_WEBSITE
    assert req.params.get("website") == "chatgpt"


def test_hebrew_open_youtube():
    req = classify_rules("פתח יוטיוב")
    assert req.intent == Intent.OPEN_WEBSITE
    assert req.params.get("website") == "youtube"


def test_tray_website_commands_safe():
    from brain.intent_classifier import classify_rules
    from config import CONFIRMATION_REQUIRED_INTENTS

    for key in ("open_chatgpt", "open_tradingview", "open_youtube", "open_gmail"):
        cmd = TRAY_MENU_COMMANDS[key]
        req = classify_rules(cmd)
        assert req.intent == Intent.OPEN_WEBSITE
        assert req.intent.value not in TRAY_FORBIDDEN_INTENTS
        assert req.intent.value not in CONFIRMATION_REQUIRED_INTENTS


def test_open_arbitrary_url_rejected(registry):
    result = OpenWebsiteAction().execute(
        CommandRequest(
            raw_text="open https://evil.com",
            intent=Intent.OPEN_WEBSITE,
            params={"website": "https://evil.com"},
        )
    )
    assert result.status in {ActionStatus.FAILED, ActionStatus.CLARIFICATION_NEEDED}
