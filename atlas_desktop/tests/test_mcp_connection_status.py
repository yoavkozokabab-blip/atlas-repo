from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_desktop import agent_integrations, data_paths, mcp_connection_status, runtime_startup, server
from atlas_desktop.mcp_server import runtime as mcp_runtime


@pytest.fixture()
def mcp_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "atlas-data"
    monkeypatch.setenv("ATLAS_DESKTOP_DATA", str(data_dir))
    data_paths.reset_desktop_data_dir_cache()
    identity = {
        "product": runtime_startup.PRODUCT,
        "protocol": runtime_startup.PROTOCOL,
        "port": 8788,
        "pid": 12345,
        "instance_id": "desktop-test-instance",
        "started_at": "2026-07-16T00:00:00Z",
    }
    runtime_startup.write_runtime_descriptor(identity, data_dir=str(data_dir))
    mcp_connection_status.reset_for_tests(data_dir=str(data_dir))
    mcp_runtime._close_current_session("test_reset")
    yield data_dir
    mcp_runtime._close_current_session("test_reset")
    mcp_connection_status.reset_for_tests(data_dir=str(data_dir))
    data_paths.reset_desktop_data_dir_cache()


def _clients(data_dir: Path, now: float = 1000.0):
    return mcp_connection_status.connections_payload(data_dir=str(data_dir), now=now)["clients"]


def test_config_exists_without_mcp_session_is_not_connected(mcp_data_dir, monkeypatch):
    monkeypatch.setattr(agent_integrations, "cursor_config_status", lambda: {"atlas_configured": True})
    monkeypatch.setattr(agent_integrations, "claude_config_status", lambda: {"atlas_configured": False})
    monkeypatch.setattr(agent_integrations, "codex_config_status", lambda: {"atlas_configured": False})
    status = agent_integrations.mcp_setup_status()
    assert status["cursor"]["atlas_configured"] is True
    assert status["cursor"]["connected"] is False
    assert status["cursor"]["connection"] == {"connected": False}


def test_clicking_connect_alone_does_not_set_connected(mcp_data_dir, monkeypatch, tmp_path):
    config = tmp_path / "mcp.json"
    monkeypatch.setattr(agent_integrations, "cursor_config_path", lambda: str(config))
    monkeypatch.setattr(agent_integrations, "atlas_executable_path", lambda: str(tmp_path / "Atlas.exe"))
    (tmp_path / "Atlas.exe").write_text("", encoding="utf-8")
    result = agent_integrations.write_cursor_config(confirm=True)
    assert result["ok"] is True
    status = agent_integrations.mcp_setup_status()
    assert status["cursor"]["atlas_configured"] is True
    assert status["cursor"]["connected"] is False


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Cursor", "cursor"),
        ("Claude Code", "claude"),
        ("Claude Desktop", "claude"),
        ("Codex", "codex"),
    ],
)
def test_initialize_marks_known_client_connected(mcp_data_dir, name, key):
    mcp_connection_status.record_initialize(
        {"name": name, "version": "1.2.3"},
        session_id=f"{key}-session",
        data_dir=str(mcp_data_dir),
        now=1000.0,
    )
    clients = _clients(mcp_data_dir, now=1005.0)
    assert clients[key]["connected"] is True
    assert clients[key]["client_name"] == name
    for other in {"cursor", "claude", "codex"} - {key}:
        assert clients[other]["connected"] is False


def test_unknown_client_does_not_mark_named_clients_connected(mcp_data_dir):
    mcp_connection_status.record_initialize(
        {"name": "Some Editor", "version": "9"},
        session_id="other-session",
        data_dir=str(mcp_data_dir),
        now=1000.0,
    )
    payload = mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir), now=1005.0)
    assert payload["other_clients_connected"] == 1
    assert all(not payload["clients"][key]["connected"] for key in ("cursor", "claude", "codex"))


def test_stream_close_marks_only_that_client_not_connected(mcp_data_dir):
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="cursor-1", data_dir=str(mcp_data_dir), now=1000.0)
    mcp_connection_status.record_initialize({"name": "Codex"}, session_id="codex-1", data_dir=str(mcp_data_dir), now=1000.0)
    mcp_connection_status.disconnect_session("cursor-1", "stream_closed", data_dir=str(mcp_data_dir), now=1010.0)
    clients = _clients(mcp_data_dir, now=1011.0)
    assert clients["cursor"]["connected"] is False
    assert clients["cursor"]["disconnect_reason"] == "stream_closed"
    assert clients["codex"]["connected"] is True


def test_restart_instance_clears_stale_connected_state(mcp_data_dir):
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="cursor-1", data_dir=str(mcp_data_dir), now=1000.0)
    old = mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir), now=1001.0)
    new = mcp_connection_status.connections_payload(
        data_dir=str(mcp_data_dir),
        current_instance_id="new-desktop-instance",
        now=1001.0,
    )
    assert old["clients"]["cursor"]["connected"] is True
    assert new["clients"]["cursor"]["connected"] is False


def test_reconnect_restores_connected(mcp_data_dir):
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="old", data_dir=str(mcp_data_dir), now=1000.0)
    mcp_connection_status.disconnect_session("old", "stream_closed", data_dir=str(mcp_data_dir), now=1001.0)
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="new", data_dir=str(mcp_data_dir), now=1002.0)
    clients = _clients(mcp_data_dir, now=1003.0)
    assert clients["cursor"]["connected"] is True
    assert clients["cursor"]["session_count"] == 1


def test_multiple_clients_and_same_client_sessions(mcp_data_dir):
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="cursor-1", data_dir=str(mcp_data_dir), now=1000.0)
    mcp_connection_status.record_initialize({"name": "Cursor"}, session_id="cursor-2", data_dir=str(mcp_data_dir), now=1001.0)
    mcp_connection_status.record_initialize({"name": "Claude Desktop"}, session_id="claude-1", data_dir=str(mcp_data_dir), now=1001.0)
    clients = _clients(mcp_data_dir, now=1002.0)
    assert clients["cursor"]["connected"] is True
    assert clients["cursor"]["session_count"] == 2
    assert clients["claude"]["connected"] is True

    mcp_connection_status.disconnect_session("cursor-1", "stream_closed", data_dir=str(mcp_data_dir), now=1003.0)
    clients = _clients(mcp_data_dir, now=1004.0)
    assert clients["cursor"]["connected"] is True
    assert clients["cursor"]["session_count"] == 1

    mcp_connection_status.disconnect_session("cursor-2", "stream_closed", data_dir=str(mcp_data_dir), now=1005.0)
    clients = _clients(mcp_data_dir, now=1006.0)
    assert clients["cursor"]["connected"] is False
    assert clients["claude"]["connected"] is True


def test_stale_session_cleanup(mcp_data_dir):
    mcp_connection_status.record_initialize({"name": "Codex"}, session_id="codex-1", data_dir=str(mcp_data_dir), now=1000.0)
    payload = mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir), now=1070.0, stale_timeout_seconds=60)
    assert payload["clients"]["codex"]["connected"] is False
    assert payload["clients"]["codex"]["disconnect_reason"] == "stale_timeout"


def test_dead_mcp_child_process_disconnects_promptly(mcp_data_dir, monkeypatch):
    monkeypatch.setattr(mcp_connection_status, "_process_is_alive", lambda _pid: False)
    mcp_connection_status.record_initialize(
        {"name": "Cursor"},
        session_id="cursor-dead-process",
        data_dir=str(mcp_data_dir),
        now=1000.0,
        pid=987654,
    )
    payload = mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir), now=1001.0, stale_timeout_seconds=60)
    assert payload["clients"]["cursor"]["connected"] is False
    assert payload["clients"]["cursor"]["disconnect_reason"] == "process_exited"


def test_idle_open_transport_over_sixty_seconds_remains_connected(mcp_data_dir):
    mcp_connection_status.record_initialize(
        {"name": "Cursor", "version": "1.0"},
        session_id="cursor-idle",
        data_dir=str(mcp_data_dir),
        now=1000.0,
    )
    mcp_connection_status.touch_session(
        "cursor-idle",
        data_dir=str(mcp_data_dir),
        now=1065.0,
        transport_only=True,
    )
    payload = mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir), now=1066.0, stale_timeout_seconds=60)
    assert payload["clients"]["cursor"]["connected"] is True
    assert payload["clients"]["cursor"]["last_seen_at"] == "1970-01-01T00:16:40Z"


def test_status_api_exposes_no_secrets_or_private_paths(mcp_data_dir):
    mcp_connection_status.record_initialize(
        {"name": "Cursor", "version": "1.0"},
        session_id="cursor-secret-safe",
        data_dir=str(mcp_data_dir),
        now=1000.0,
    )
    status_code, payload = server.dispatch("GET", "/api/mcp/connections")
    assert status_code == 200
    text = json.dumps(payload)
    assert "clients" in payload
    assert str(mcp_data_dir) not in text
    assert "Atlas.exe" not in text
    assert "command" not in text.lower()
    assert "secret" not in text.lower()
    assert "session_id" not in text


def test_runtime_initialize_and_exit_updates_connection_status(mcp_data_dir):
    response = mcp_runtime.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "Cursor", "version": "1.0"}},
        }
    )
    assert response and response["result"]["serverInfo"]["name"] == "atlas-local"
    assert mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir))["clients"]["cursor"]["connected"] is True

    assert mcp_runtime.handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/exit"}) is None
    assert mcp_connection_status.connections_payload(data_dir=str(mcp_data_dir))["clients"]["cursor"]["connected"] is False


def test_ui_uses_active_status_and_non_aggressive_polling():
    js = (Path(__file__).resolve().parents[1] / "static" / "atlas_mcp_setup.js").read_text(encoding="utf-8")
    assert 'connected ? "Connected" : "Not connected"' in js
    assert "atlas_configured" in js
    assert "POLL_INTERVAL_MS = 8000" in js
    assert "setInterval" not in js
    assert "startConnectionPolling" in js
