"""MCP one-click setup and installed-exe diagnostics tests."""

from __future__ import annotations

import json
from pathlib import Path

from jarvis_desktop import agent_integrations as ai


def test_mcp_snippet_uses_atlas_exe_when_available(tmp_path, monkeypatch):
    installed = tmp_path / "Programs" / "Atlas" / "Atlas.exe"
    installed.parent.mkdir(parents=True)
    installed.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(ai, "atlas_executable_path", lambda: str(installed))
    snippet = ai.mcp_snippet()["mcpServers"]["atlas"]
    assert snippet["command"] == str(installed)
    assert snippet["args"] == ["--mcp"]


def test_cursor_config_write_preserves_existing_servers(tmp_path, monkeypatch):
    cursor_dir = tmp_path / ".cursor"
    config = cursor_dir / "mcp.json"
    cursor_dir.mkdir(parents=True)
    config.write_text(
        json.dumps({"mcpServers": {"existing": {"command": "tool", "args": ["--ok"]}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ai, "cursor_config_path", lambda: str(config))
    monkeypatch.setattr(ai, "atlas_executable_path", lambda: str(tmp_path / "Atlas.exe"))
    (tmp_path / "Atlas.exe").write_text("", encoding="utf-8")

    denied = ai.write_cursor_config(confirm=False)
    assert denied["ok"] is False

    written = ai.write_cursor_config(confirm=True)
    assert written["ok"] is True
    assert written.get("backup_path")
    data = json.loads(config.read_text(encoding="utf-8"))
    assert "existing" in data["mcpServers"]
    assert data["mcpServers"]["atlas"]["args"] == ["--mcp"]


def test_claude_config_write_preserves_existing_servers(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData" / "Roaming"
    config = appdata / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps({"mcpServers": {"existing": {"command": "tool", "args": ["--ok"]}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setattr(ai, "atlas_executable_path", lambda: str(tmp_path / "Atlas.exe"))
    (tmp_path / "Atlas.exe").write_text("", encoding="utf-8")

    written = ai.write_claude_config(confirm=True)
    assert written["ok"] is True
    data = json.loads(config.read_text(encoding="utf-8"))
    assert "existing" in data["mcpServers"]
    assert "atlas" in data["mcpServers"]


def test_run_mcp_diagnostics_reports_checks(monkeypatch):
    monkeypatch.setattr(ai, "atlas_executable_path", lambda: "C:/missing/Atlas.exe")
    monkeypatch.setattr(
        ai,
        "test_mcp_runtime",
        lambda: {"ok": True, "tool_count": 3, "tools": ["atlas_health"]},
    )
    result = ai.run_mcp_diagnostics()
    assert "checks" in result
    names = {item["name"] for item in result["checks"]}
    assert "Atlas executable path resolved" in names
    assert "Atlas MCP runtime loads tools" in names


def test_run_atlas_source_declares_mcp_flag():
    root = Path(__file__).resolve().parents[2]
    text = (root / "run_atlas.py").read_text(encoding="utf-8")
    assert '"--mcp"' in text or "'--mcp'" in text
