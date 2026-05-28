"""Phase 15 safe app launcher tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.app_actions import OpenAppAction
from apps.app_registry import AppRegistry, ApprovedApp
from apps.discovery import DiscoveredApp, discover_installed_apps
from apps.launcher import launch_app
from apps.safety import SafetyError, validate_launch_path
from brain.router import CommandRouter
from core import confirmation
from core.types import ActionStatus, CommandRequest, Intent


@pytest.fixture
def menu_root(tmp_path: Path) -> Path:
    root = tmp_path / "Start Menu" / "Programs"
    root.mkdir(parents=True)
    discord = root / "Discord.lnk"
    discord.write_bytes(b"LocalBasePathC:\\Apps\\Discord\\Discord.exe\x00")
    spotify = root / "Spotify.lnk"
    spotify.write_bytes(b"LocalBasePathC:\\Apps\\Spotify\\Spotify.exe\x00")
    blocked = root / "PowerShell.lnk"
    blocked.write_bytes(b"LocalBasePathC:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\x00")
    return root


@pytest.fixture
def registry(tmp_path: Path, monkeypatch) -> AppRegistry:
    path = tmp_path / "approved_apps.json"
    monkeypatch.setattr("apps.app_registry.APPROVED_APPS_PATH", path)
    monkeypatch.setattr("config.APPROVED_APPS_PATH", path)
    return AppRegistry(path)


def test_discovery_scans_start_menu(menu_root: Path):
    apps = discover_installed_apps(start_menu_roots=[menu_root], include_registry_names=False)
    ids = {a.app_id for a in apps}
    assert "discord" in ids
    assert "spotify" in ids
    assert "powershell" not in ids


def test_blocked_executable_rejected(menu_root: Path):
    from apps.discovery import _resolve_lnk_target
    from apps.safety import validate_resolved_target

    ps = menu_root / "PowerShell.lnk"
    target = _resolve_lnk_target(ps)
    assert target is not None
    with pytest.raises(SafetyError):
        validate_resolved_target(target)


def test_launch_uses_startfile_not_shell(menu_root: Path):
    lnk = menu_root / "Discord.lnk"
    with patch("apps.launcher.os.startfile") as startfile:
        msg = launch_app(shortcut_path=lnk, display_name="Discord")
    startfile.assert_called_once()
    assert "Opened Discord" in msg
    # Ensure no subprocess shell
    with patch("apps.launcher.os.startfile") as startfile2:
        launch_app(shortcut_path=lnk, display_name="Discord")
    startfile2.assert_called_once()


def test_open_approved_app_skips_confirmation(registry: AppRegistry, menu_root: Path):
    lnk = menu_root / "Discord.lnk"
    registry.approve(
        ApprovedApp(
            app_id="discord",
            display_name="Discord",
            shortcut_path=lnk.resolve(),
        )
    )
    req = MagicMock(
        intent=Intent.OPEN_APP,
        raw_text="open discord",
        params={"app": "discord"},
        confirmed=False,
    )
    with patch("actions.app_actions.launch_approved", return_value="Opened Discord."):
        result = OpenAppAction().execute(req)
    assert result.status == ActionStatus.SUCCESS


def test_unknown_app_requires_confirmation(registry: AppRegistry, menu_root: Path):
    req = MagicMock(
        intent=Intent.OPEN_APP,
        raw_text="open discord",
        params={"app": "discord"},
        confirmed=False,
    )
    app = DiscoveredApp(
        app_id="discord",
        display_name="Discord",
        shortcut_path=(menu_root / "Discord.lnk").resolve(),
    )
    with patch(
        "actions.app_actions.find_best_match",
        return_value=([app], "discord"),
    ):
        result = OpenAppAction().execute(req)
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert "Approve and open Discord" in result.summary


def test_multiple_matches_clarify(registry: AppRegistry, menu_root: Path):
    apps = [
        DiscoveredApp("discord", "Discord", (menu_root / "Discord.lnk").resolve()),
        DiscoveredApp("discord_beta", "Discord Beta", (menu_root / "Spotify.lnk").resolve()),
    ]
    req = MagicMock(
        intent=Intent.OPEN_APP,
        raw_text="open discord",
        params={"app": "discord"},
        confirmed=False,
    )
    with patch("actions.app_actions.find_best_match", return_value=(apps, "discord")):
        result = OpenAppAction().execute(req)
    assert result.status == ActionStatus.CLARIFICATION_NEEDED


def test_confirm_approves_and_opens(registry: AppRegistry, menu_root: Path):
    lnk = (menu_root / "Discord.lnk").resolve()
    app = DiscoveredApp("discord", "Discord", lnk)
    cid = confirmation.create_confirmation(
        "open_app",
        {
            "raw_text": "open discord",
            "params": {"app": "discord", "discovered": app.to_dict()},
        },
    )
    req = CommandRequest(
        raw_text="yes",
        intent=Intent.OPEN_APP,
        params={"discovered": app.to_dict(), "app_id": "discord"},
        confirmed=True,
        confirmation_id=cid,
    )
    confirmation.confirm(cid)
    with patch("actions.app_actions.find_best_match", return_value=([], "discord")):
        with patch("actions.app_actions.launch_discovered", return_value="Opened Discord."):
            result = OpenAppAction().execute(req)
    assert result.status == ActionStatus.SUCCESS
    assert registry.get("discord") is not None


def test_forget_app_removes_approval(registry: AppRegistry, menu_root: Path):
    lnk = (menu_root / "Discord.lnk").resolve()
    registry.approve(
        ApprovedApp(app_id="discord", display_name="Discord", shortcut_path=lnk)
    )
    from actions.app_actions import ForgetAppAction

    result = ForgetAppAction().execute(
        MagicMock(intent=Intent.FORGET_APP, raw_text="forget discord", params={"app": "discord"})
    )
    assert result.status == ActionStatus.SUCCESS
    assert registry.get("discord") is None


def test_router_open_app_path(menu_root: Path, registry: AppRegistry, monkeypatch):
    monkeypatch.setattr("apps.app_registry.APPROVED_APPS_PATH", registry.path)
    lnk = (menu_root / "Discord.lnk").resolve()
    registry.approve(
        ApprovedApp(app_id="discord", display_name="Discord", shortcut_path=lnk)
    )
    router = CommandRouter()
    with patch("apps.discovery.discover_installed_apps") as disc:
        disc.return_value = []
        with patch("apps.launcher.os.startfile"):
            result = router.route("open discord")
    assert result.intent == Intent.OPEN_APP
    assert result.status == ActionStatus.SUCCESS


def test_classify_open_discord():
    from brain.intent_classifier import classify_rules

    req = classify_rules("open discord")
    assert req.intent == Intent.OPEN_APP
    assert req.params.get("app") == "discord"


def test_hebrew_open_discord():
    from brain.intent_classifier import classify_rules

    req = classify_rules("פתח דיסקורד")
    assert req.intent == Intent.OPEN_APP
    assert req.params.get("app") == "discord"


def test_approval_persists(registry: AppRegistry, menu_root: Path):
    lnk = (menu_root / "Discord.lnk").resolve()
    registry.approve(
        ApprovedApp(app_id="discord", display_name="Discord", shortcut_path=lnk)
    )
    data = json.loads(registry.path.read_text(encoding="utf-8"))
    assert "discord" in data["apps"]
