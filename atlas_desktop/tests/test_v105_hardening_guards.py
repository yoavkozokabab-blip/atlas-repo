"""v1.0.5 hardening guards: subprocess safety + analytics resilience."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_ROOT = Path(__file__).resolve().parents[2]


def _iter_source(*roots):
    for root in roots:
        base = _ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            parts = set(path.parts)
            if ".lib" in parts or "tests" in parts or "__pycache__" in parts:
                continue
            yield path


def test_no_subprocess_uses_shell_true():
    """Every subprocess invocation must pass an argument array, never a shell
    string, so repository/config-controlled values can't be interpreted by a
    shell."""
    offenders = []
    for path in _iter_source("atlas_desktop", "accounts_service"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        offenders.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    assert not offenders, "shell=True found: " + ", ".join(offenders)


def test_no_os_system_calls():
    offenders = []
    for path in _iter_source("atlas_desktop", "accounts_service"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "system" and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    offenders.append(f"{path.relative_to(_ROOT)}:{node.lineno}")
    assert not offenders, "os.system found: " + ", ".join(offenders)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "atlas_data"
    d.mkdir()
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(d))
    from atlas_desktop.data_paths import reset_desktop_data_dir_cache
    reset_desktop_data_dir_cache()
    return str(d)


def test_analytics_write_failure_never_raises(data_dir, monkeypatch):
    """An analytics write error must degrade gracefully, never propagate."""
    from atlas_desktop import analytics

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _boom)
    result = analytics.track_event("impact_completed", duration_ms=12)
    assert result["ok"] is False
    assert result["analytics_status"] == "degraded"
    assert result["error"] == "analytics_unavailable"


def test_analytics_happy_path_reports_ok(data_dir):
    from atlas_desktop import analytics

    result = analytics.track_event("app_screen_viewed", screen="impact")
    assert result["ok"] is True
    assert result["analytics_status"] == "ok"


def test_analytics_requires_event_name(data_dir):
    from atlas_desktop import analytics

    assert analytics.track_event("").get("ok") is False
