"""Alias store tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from brain.aliases import AliasStore, reset_alias_store
from brain.router import CommandRouter
from brain.storage_safe import UnsafeStorageError
from config import CONFIRMATION_REQUIRED_INTENTS
from core.types import ActionStatus, Intent


@pytest.fixture
def alias_store(tmp_path: Path, monkeypatch):
    reset_alias_store()
    path = tmp_path / "aliases.json"
    backups = tmp_path / "backups"
    monkeypatch.setattr("brain.aliases.ALIASES_PATH", path)
    monkeypatch.setattr("brain.aliases.BACKUPS_DIR", backups)
    store = AliasStore(path)
    yield store
    reset_alias_store()


def test_alias_resolves_implemented_intent(alias_store: AliasStore):
    alias_store.add_alias("פתח מסחר", "open_trading_dashboard")
    req = alias_store.resolve_alias("פתח מסחר")
    assert req is not None
    assert req.intent == Intent.OPEN_TRADING_DASHBOARD
    assert req.classifier_source == "alias"


def test_alias_unknown_intent_rejected(alias_store: AliasStore):
    with pytest.raises(UnsafeStorageError):
        alias_store.add_alias("bad", "open_task_manager")


def test_alias_confirmation_still_required(alias_store: AliasStore):
    alias_store.add_alias("run daily", "run_live_daily_loop")
    req = alias_store.resolve_alias("run daily")
    assert req.intent.value in CONFIRMATION_REQUIRED_INTENTS


def test_alias_no_shell(alias_store: AliasStore):
    with pytest.raises(UnsafeStorageError):
        alias_store.add_alias("hack", "open_cursor", params={"cmd": "powershell rm"})


def test_hebrew_alias_and_delete(alias_store: AliasStore):
    alias_store.add_alias("פתח מסחר", "open_trading_dashboard")
    assert alias_store.resolve_alias("פתח מסחר") is not None
    assert alias_store.delete_alias("פתח מסחר")
    assert alias_store.resolve_alias("פתח מסחר") is None


def test_router_alias_passes_security(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("brain.aliases.ALIASES_PATH", tmp_path / "aliases.json")
    monkeypatch.setattr("brain.aliases.BACKUPS_DIR", tmp_path / "backups")
    reset_alias_store()
    AliasStore().add_alias("my dashboard", "open_trading_dashboard")

    router = CommandRouter()
    with (
        patch("actions.trading_dashboard.dashboard_health_reachable", return_value=True),
        patch("actions.trading_dashboard.webbrowser.open", return_value=True),
        patch("actions.trading_dashboard.run_allowlisted_script") as script,
    ):
        result = router.route("my dashboard")
    assert result.intent == Intent.OPEN_TRADING_DASHBOARD
    assert result.status == ActionStatus.SUCCESS


def test_router_alias_confirmation_required(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("brain.aliases.ALIASES_PATH", tmp_path / "aliases.json")
    monkeypatch.setattr("brain.aliases.BACKUPS_DIR", tmp_path / "backups")
    reset_alias_store()
    AliasStore().add_alias("go daily", "run_live_daily_loop")

    router = CommandRouter()
    result = router.route("go daily")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
