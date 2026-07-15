"""MCP one-click setup and installed-exe diagnostics tests."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_desktop import agent_integrations as ai


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


def test_codex_config_write_preserves_existing_servers(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    config = codex_dir / "config.toml"
    codex_dir.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                "[mcp_servers.existing]",
                "command = 'tool.exe'",
                "args = ['--ok']",
                "enabled = true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_dir))
    monkeypatch.setattr(ai, "atlas_executable_path", lambda: str(tmp_path / "Atlas.exe"))
    (tmp_path / "Atlas.exe").write_text("", encoding="utf-8")

    denied = ai.write_codex_config(confirm=False)
    assert denied["ok"] is False

    written = ai.write_codex_config(confirm=True)
    assert written["ok"] is True
    assert written.get("backup_path")
    assert written.get("message") == "Codex configured. Restart Codex to use Atlas."
    text = config.read_text(encoding="utf-8")
    assert "[mcp_servers.existing]" in text
    assert "[mcp_servers.atlas]" in text
    data, err = ai._load_codex_config(str(config))
    assert err is None
    assert ai._codex_atlas_configured(data)
    assert data["mcp_servers"]["atlas"]["args"] == ["--mcp"]


def test_codex_write_endpoint_registered():
    from atlas_desktop import server

    assert ("POST", "/api/integrations/codex/write-config") in server.ROUTES


def test_mcp_write_config_routes_are_local_not_account_gated():
    from atlas_desktop import server

    local_routes = {
        ("POST", "/api/integrations/cursor/write-config"),
        ("POST", "/api/integrations/claude/write-config"),
        ("POST", "/api/integrations/codex/write-config"),
    }
    assert local_routes.issubset(set(server.ROUTES))
    assert local_routes.isdisjoint(server.PROTECTED_ACCOUNT_ROUTES)


def test_mcp_write_config_dispatch_calls_real_handlers_without_account(monkeypatch):
    from atlas_desktop import server

    monkeypatch.setattr(
        server.accounts_client,
        "get_account_state",
        lambda: {"authenticated": False, "user": None, "license": {"valid": False}},
    )
    called = []
    monkeypatch.setattr(server.api, "write_claude_mcp_config", lambda confirm=False: called.append(("claude", confirm)) or {"ok": True, "config_path": "claude.json"})
    monkeypatch.setattr(server.api, "write_cursor_mcp_config", lambda confirm=False: called.append(("cursor", confirm)) or {"ok": True, "config_path": "cursor.json"})
    monkeypatch.setattr(server.api, "write_codex_mcp_config", lambda confirm=False: called.append(("codex", confirm)) or {"ok": True, "config_path": "config.toml"})

    for tool in ("claude", "cursor", "codex"):
        status, payload = server.dispatch("POST", f"/api/integrations/{tool}/write-config", {"confirm": True})
        assert status == 200
        assert payload["ok"] is True

    assert called == [("claude", True), ("cursor", True), ("codex", True)]


def test_fastapi_mcp_write_routes_exist_in_installed_runtime_source():
    source = (Path(__file__).resolve().parents[1] / "server.py").read_text(encoding="utf-8")
    for path in (
        "/api/integrations/cursor/write-config",
        "/api/integrations/claude/write-config",
        "/api/integrations/codex/write-config",
    ):
        assert f'@app.post("{path}")' in source


def test_connect_codex_js_uses_write_endpoint_not_clipboard():
    js = (Path(__file__).resolve().parents[1] / "static" / "atlas_mcp_setup.js").read_text(encoding="utf-8")
    connect = js[js.find("async function connectCodex"): js.find("function resetToolDetails")]
    assert "/api/integrations/codex/write-config" in connect
    assert "copyText" not in connect
    assert "copyManualConfig" not in connect


def test_primary_mcp_connect_buttons_call_api_and_do_not_copy():
    js = (Path(__file__).resolve().parents[1] / "static" / "atlas_mcp_setup.js").read_text(encoding="utf-8")
    helper = js[js.find("async function connectAgent"): js.find("async function connectCursor")]
    assert "api(endpoint, \"POST\", { confirm: true })" in helper
    for name, endpoint in {
        "connectClaude": "/api/integrations/claude/write-config",
        "connectCursor": "/api/integrations/cursor/write-config",
        "connectCodex": "/api/integrations/codex/write-config",
    }.items():
        start = js.find(f"async function {name}")
        end = js.find("\n  async function", start + 1)
        if end == -1:
            end = js.find("\n  function", start + 1)
        block = js[start:end]
        assert start != -1
        assert endpoint in block
        assert "copyText" not in block
        assert "navigator.clipboard" not in block


def test_mcp_home_section_has_per_tool_cards_not_global_actions():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    section_start = html.index('id="mcpSetupSection"')
    section_end = html.index("</section>", section_start)
    section = html[section_start:section_end]
    assert 'id="mcpClaudeCard"' in section
    assert 'id="mcpCursorCard"' in section
    assert 'id="mcpCodexCard"' in section
    assert "Test Claude" in section
    assert "Test Cursor" in section
    assert "Test Codex" in section
    assert "Manual setup" in section
    assert section.count('class="mcp-home-advanced"') == 3
    assert "Test connection" not in section
    assert "Copy MCP config" not in section
    assert 'id="mcpSetupOutput"' not in section
    assert 'id="mcpAdvanced"' not in section
