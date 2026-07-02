"""Agent integration helper tests."""

from __future__ import annotations

import json
from pathlib import Path

from jarvis_desktop import agent_integrations as ai


def _repo(root: Path) -> Path:
    (root / "app").mkdir()
    (root / "tests").mkdir()
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "auth.py").write_text(
        "API_KEY = 'SHOULD_NOT_EXPORT'\n\nclass AuthStore:\n    def login(self, token):\n        return token\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_auth.py").write_text(
        "from app.auth import AuthStore\n\ndef test_login():\n    assert AuthStore()\n",
        encoding="utf-8",
    )
    (root / ".env").write_text("ATLAS_SECRET=SHOULD_NOT_EXPORT\n", encoding="utf-8")
    return root


def test_task_export_is_compact_and_does_not_dump_source_or_env(tmp_path):
    repo = _repo(tmp_path)
    result = ai.export_for_repo(
        str(repo),
        target="codex",
        task="Fix AuthStore login token handling with Authorization: Bearer SECRET_TOKEN_VALUE",
        max_files=6,
    )
    assert result["ok"] is True
    text = result["text"]
    assert "app/auth.py" in text
    assert ".env" not in text
    assert "SHOULD_NOT_EXPORT" not in text
    assert "SECRET_TOKEN_VALUE" not in text
    assert "[REDACTED]" in text
    assert "class AuthStore" not in text
    assert result["estimated_tokens"] < 1200


def test_cursor_rule_uses_markers_and_preserves_user_content(tmp_path):
    repo = _repo(tmp_path)
    rule = repo / ".cursor" / "rules" / "atlas.md"
    rule.parent.mkdir(parents=True)
    rule.write_text("# User rules\n\nKeep this.\n", encoding="utf-8")

    result = ai.write_cursor_rule(str(repo), task="Fix AuthStore login token handling")

    assert result["ok"] is True
    text = rule.read_text(encoding="utf-8")
    assert "# User rules" in text
    assert "Keep this." in text
    assert ai.ATLAS_START in text
    assert ai.ATLAS_END in text
    assert "app/auth.py" in text


def test_claude_managed_block_preserves_handwritten_content(tmp_path):
    repo = _repo(tmp_path)
    claude = repo / "CLAUDE.md"
    claude.write_text("# Project notes\n\nHuman note.\n", encoding="utf-8")

    result = ai.write_claude_managed_block(str(repo), task="")

    assert result["ok"] is True
    text = claude.read_text(encoding="utf-8")
    assert "# Project notes" in text
    assert "Human note." in text
    assert ai.ATLAS_START in text
    assert ai.ATLAS_END in text
    assert "See AGENTS.md" in text


def test_claude_config_write_preserves_existing_servers(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData" / "Roaming"
    config = appdata / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps({"mcpServers": {"existing": {"command": "tool", "args": ["--ok"]}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("APPDATA", str(appdata))

    denied = ai.write_claude_config(confirm=False)
    assert denied["ok"] is False
    assert denied["code"] == "confirmation_required"

    written = ai.write_claude_config(confirm=True)
    assert written["ok"] is True
    data = json.loads(config.read_text(encoding="utf-8"))
    assert "existing" in data["mcpServers"]
    assert "atlas" in data["mcpServers"]
    assert Path(data["mcpServers"]["atlas"]["args"][0]).name == "run_atlas.py"


def test_discover_claude_paths_includes_appdata_and_store(tmp_path, monkeypatch):
    appdata = tmp_path / "AppData" / "Roaming"
    local = tmp_path / "AppData" / "Local"
    store_pkg = local / "Packages" / "AnthropicClaude_8wekyb3d8bbwe"
    store_config = store_pkg / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json"
    store_config.parent.mkdir(parents=True)
    store_config.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    discovered = ai.discover_claude_desktop_config_paths()
    sources = {d["source"] for d in discovered}
    paths = {d["path"] for d in discovered}
    assert "appdata_roaming" in sources
    assert "microsoft_store:AnthropicClaude_8wekyb3d8bbwe" in sources
    assert str(store_config) in paths
    assert ai.claude_desktop_config_path() == str(store_config)


def test_claude_status_reports_discovered_paths(tmp_path, monkeypatch):
    appdata = tmp_path / "Roaming"
    config = appdata / "Claude" / "claude_desktop_config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"mcpServers": {}}', encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))

    status = ai.claude_config_status()
    assert status["config_path"] == str(config)
    assert len(status["discovered_paths"]) >= 1
    assert status["config_source"] == "appdata_roaming"
