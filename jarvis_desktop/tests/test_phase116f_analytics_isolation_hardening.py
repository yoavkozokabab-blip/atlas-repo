"""Phase 116F — analytics must never break scan or demo load."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from jarvis_desktop import analytics, api


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _small_repo(tmp_path: Path) -> Path:
    root = tmp_path / "small"
    _write(root / "core" / "hub.py", "def hub():\n    return 1\n")
    for name in ("a", "b"):
        _write(root / f"{name}.py", f"from core.hub import hub\n\ndef run_{name}():\n    return hub()\n")
    return root


@pytest.fixture(autouse=True)
def isolated_analytics(tmp_path, monkeypatch):
    data_dir = tmp_path / "analytics_data"
    data_dir.mkdir()
    monkeypatch.setenv("JARVIS_DESKTOP_DATA", str(data_dir))
    analytics.reset_analytics_for_tests()


@pytest.fixture()
def clean_scan_state():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    yield
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})


def _deny_analytics_append(monkeypatch):
    real_open = builtins.open

    def guarded_open(path, mode="r", *args, **kwargs):
        if "a" in mode and str(path).replace("\\", "/").endswith("analytics.jsonl"):
            raise PermissionError(13, "Access is denied", str(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)


def test_track_event_does_not_raise_on_permission_error(monkeypatch):
    _deny_analytics_append(monkeypatch)
    result = analytics.track_event("probe")
    assert result["ok"] is False
    assert result["analytics_status"] == "degraded"
    assert "Telemetry unavailable" in result["telemetry_warning"]


def test_scan_succeeds_when_analytics_write_fails(monkeypatch, tmp_path, clean_scan_state):
    _deny_analytics_append(monkeypatch)
    root = _small_repo(tmp_path)
    result = api.scan_repository(str(root))
    assert result["ok"] is True
    assert result.get("module_count", 0) >= 1
    assert result["analytics_status"] == "degraded"
    assert result.get("telemetry_warning")


def test_demo_succeeds_when_analytics_write_fails(monkeypatch, clean_scan_state):
    _deny_analytics_append(monkeypatch)
    result = api.load_demo_mode("small")
    assert result["ok"] is True
    assert result.get("demo_mode") is True
    assert result["analytics_status"] == "degraded"
    assert result.get("telemetry_warning")


def test_scan_succeeds_when_analytics_directory_cannot_be_created(monkeypatch, tmp_path, clean_scan_state):
    def deny_makedirs(*_args, **_kwargs):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(analytics.os, "makedirs", deny_makedirs)
    root = _small_repo(tmp_path)
    result = api.scan_repository(str(root))
    assert result["ok"] is True
    assert result["analytics_status"] == "degraded"


def test_health_reports_degraded_telemetry_after_write_failure(monkeypatch, tmp_path, clean_scan_state):
    _deny_analytics_append(monkeypatch)
    api.scan_repository(str(_small_repo(tmp_path)))
    health = api.health()
    assert health["analytics_status"] == "degraded"
    assert health.get("telemetry_warning")


def test_summary_reports_degraded_telemetry_after_write_failure(monkeypatch, tmp_path, clean_scan_state):
    _deny_analytics_append(monkeypatch)
    api.scan_repository(str(_small_repo(tmp_path)))
    summary = api.current_summary()
    assert summary["ok"] is True
    assert summary["analytics_status"] == "degraded"
    assert summary.get("telemetry_warning")
