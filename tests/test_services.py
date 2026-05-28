"""Phase 11 services tests (autostart, health, watchdog)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from actions.service_actions import (
    EnableAutostartAction,
    RunJarvisHealthCheckAction,
    ShowAutostartStatusAction,
)
from brain.intent_classifier import classify_rules
from brain.router import CommandRouter
from config import CONFIRMATION_REQUIRED_INTENTS
from core.types import ActionStatus, CommandRequest, Intent
from services.autostart import (
    TRAY_LAUNCH_SCRIPT,
    AutostartError,
    disable_autostart,
    enable_autostart,
    get_autostart_status,
    validate_tray_script_path,
)
from services.health import run_jarvis_health_check
from services.watchdog import WatchdogService


def test_autostart_intents_require_confirmation():
    assert "enable_autostart" in CONFIRMATION_REQUIRED_INTENTS
    assert "disable_autostart" in CONFIRMATION_REQUIRED_INTENTS
    assert "show_autostart_status" not in CONFIRMATION_REQUIRED_INTENTS


def test_hebrew_classifier_mappings():
    assert classify_rules("תפעיל הפעלה אוטומטית").intent == Intent.ENABLE_AUTOSTART
    assert classify_rules("מצב הפעלה אוטומטית").intent == Intent.SHOW_AUTOSTART_STATUS
    assert classify_rules("בדוק את ג'רוויס").intent == Intent.RUN_JARVIS_HEALTH_CHECK
    assert classify_rules("מה מצב watchdog").intent == Intent.SHOW_WATCHDOG_STATUS


def test_validate_tray_script_rejects_unsafe_path(tmp_path: Path):
    bad = tmp_path / "evil.ps1"
    bad.write_text("bad", encoding="utf-8")
    with pytest.raises(AutostartError, match="Unsafe"):
        validate_tray_script_path(bad)


def test_tray_script_path_is_project_script():
    assert TRAY_LAUNCH_SCRIPT.name == "run_jarvis_tray.ps1"
    assert "scripts" in TRAY_LAUNCH_SCRIPT.parts


def test_enable_autostart_calls_powershell_with_safe_script(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "services.autostart.TRAY_LAUNCH_SCRIPT",
        tmp_path / "scripts" / "run_jarvis_tray.ps1",
    )
    script = tmp_path / "scripts" / "run_jarvis_tray.ps1"
    script.parent.mkdir(parents=True)
    script.write_text("# tray", encoding="utf-8")
    monkeypatch.setattr("services.autostart.PROJECT_ROOT", tmp_path)

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0, stderr="")

    monkeypatch.setattr("services.autostart.subprocess.run", fake_run)
    monkeypatch.setattr(
        "services.autostart._startup_folder",
        lambda: tmp_path / "Startup",
    )
    monkeypatch.setattr(
        "services.autostart._shortcut_path",
        lambda: tmp_path / "Startup" / "JARVIS Tray.lnk",
    )
    monkeypatch.setattr("services.autostart._read_shortcut_target", lambda p: {})

    enable_autostart()
    assert calls
    joined = " ".join(calls[0])
    assert "run_jarvis_tray.ps1" in joined
    assert "evil" not in joined


def test_router_enable_autostart_requires_confirmation():
    router = CommandRouter()
    result = router.route("enable autostart")
    assert result.status == ActionStatus.CONFIRMATION_REQUIRED
    assert result.confirmation_id


def test_health_detects_missing_tesseract(monkeypatch):
    monkeypatch.setattr("services.health.VISION_ENABLED", True)
    monkeypatch.setattr("services.health._tesseract_available", lambda: False)
    monkeypatch.setattr("services.health.LLM_CLASSIFIER_ENABLED", False)
    report = run_jarvis_health_check()
    names = [c.name for c in report.checks]
    assert "tesseract" in names
    tesseract = next(c for c in report.checks if c.name == "tesseract")
    assert tesseract.status == "warning"


def test_health_detects_ollama_unreachable(monkeypatch):
    monkeypatch.setattr("services.health.VISION_ENABLED", False)
    monkeypatch.setattr("services.health.LLM_CLASSIFIER_ENABLED", True)
    monkeypatch.setattr("services.health._ollama_reachable", lambda: (False, "connection refused"))
    report = run_jarvis_health_check()
    ollama = next(c for c in report.checks if c.name == "ollama")
    assert ollama.status == "critical"


def test_watchdog_writes_status(tmp_path: Path, monkeypatch):
    status_file = tmp_path / "watchdog_status.json"
    tray = MagicMock()
    tray.runtime = MagicMock(running=True, voice_enabled=False, tray_enabled=True, last_error=None)
    tray._voice_thread = None
    tray._icon = None

    report = MagicMock()
    report.overall = "ok"
    report.summary = "ok"
    report.checked_at = "2020-01-01T00:00:00Z"
    report.to_dict.return_value = {"checks": []}
    report.checks = []

    with patch("services.watchdog.run_jarvis_health_check", return_value=report):
        wd = WatchdogService(tray, interval_seconds=1, status_path=status_file)
        payload = wd.run_once()

    assert status_file.is_file()
    assert payload["repairs_performed"] is False
    on_disk = json.loads(status_file.read_text(encoding="utf-8"))
    assert on_disk["overall"] == "ok"


def test_watchdog_notifies_on_critical(monkeypatch, tmp_path: Path):
    tray = MagicMock()
    tray.runtime = MagicMock(running=True, voice_enabled=True, tray_enabled=True, last_error="x")
    tray._voice_thread = None
    tray._icon = None

    from services.health import HealthCheckItem, HealthReport

    report = HealthReport(
        overall="critical",
        checks=[
            HealthCheckItem("ollama", "critical", "down"),
        ],
        summary="critical",
        checked_at="t",
    )

    with (
        patch("services.watchdog.run_jarvis_health_check", return_value=report),
        patch("ui.notifications.notify") as notify,
    ):
        wd = WatchdogService(tray, status_path=tmp_path / "s.json")
        wd.run_once()

    notify.assert_called_once()


def test_watchdog_recovery_stays_in_process():
    root = Path(__file__).resolve().parent.parent
    text = (root / "services" / "watchdog.py").read_text(encoding="utf-8").lower()
    assert "recovery_enabled" in text
    assert "subprocess.run" not in text
    assert "kill" not in text


def test_show_autostart_status_read_only():
    with patch("services.autostart.get_autostart_status") as status:
        status.return_value = {
            "enabled": False,
            "shortcut_path": "x",
            "tray_script": str(TRAY_LAUNCH_SCRIPT),
            "tray_script_exists": True,
            "method": "windows_startup_shortcut",
        }
        result = ShowAutostartStatusAction().execute(
            CommandRequest(raw_text="status", intent=Intent.SHOW_AUTOSTART_STATUS)
        )
    assert result.status == ActionStatus.SUCCESS


def test_disable_autostart_removes_shortcut(monkeypatch, tmp_path: Path):
    handle = tempfile.NamedTemporaryFile(suffix=".lnk", dir=tmp_path, delete=True)
    handle.flush()
    shortcut = Path(handle.name)
    state = {"handle": handle}

    def _sandbox_delete(target: Path) -> bool:
        assert Path(target) == shortcut
        live = state.get("handle")
        if live is not None:
            live.close()
            state["handle"] = None
        return not shortcut.exists()

    monkeypatch.setattr("services.autostart._shortcut_path", lambda: shortcut)
    monkeypatch.setattr("services.autostart._read_shortcut_target", lambda p: {})
    monkeypatch.setattr("services.autostart.remove_file_best_effort", _sandbox_delete)
    try:
        disable_autostart()
        assert not shortcut.exists()
    finally:
        live = state.get("handle")
        if live is not None:
            live.close()


def test_run_jarvis_health_check_action():
    with patch("actions.service_actions.run_jarvis_health_check") as run:
        from services.health import HealthReport

        run.return_value = HealthReport(overall="ok", summary="all ok", checked_at="t")
        result = RunJarvisHealthCheckAction().execute(
            CommandRequest(raw_text="health", intent=Intent.RUN_JARVIS_HEALTH_CHECK)
        )
    assert result.status == ActionStatus.SUCCESS
    assert "data" in result.model_dump() or result.data
