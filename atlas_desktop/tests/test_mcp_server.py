"""Atlas MCP server tests."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from atlas_desktop import api, mcp_server as mcp


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "scan_cache": {},
            "session_export": None,
            "repository_memory": None,
            "_current_memory": None,
            "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
            "last_scope": {"mode": "entire_repo"},
        }
    )


def _small_repo(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "auth.py").write_text(
        "class AuthStore:\n    def login(self, token):\n        return token\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "routes.py").write_text(
        "from app.auth import AuthStore\n\nhandler = AuthStore()\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_auth.py").write_text(
        "from app.auth import AuthStore\n\ndef test_login():\n    assert AuthStore()\n",
        encoding="utf-8",
    )
    return tmp_path


def test_mcp_tool_schemas_are_stable_and_read_only():
    listed = mcp.list_tools()["tools"]
    names = {tool["name"] for tool in listed}
    required = {
        "atlas_scan_repo",
        "atlas_repo_summary",
        "atlas_get_architecture",
        "atlas_get_dependency_graph",
        "atlas_find_relevant_files",
        "atlas_get_codebase_map",
        "atlas_build_context_pack",
        "atlas_what_breaks",
        "atlas_get_impact_analysis",
        "atlas_plan_change",
        "atlas_get_change_plan",
        "atlas_find_file",
        "atlas_repo_health",
        "atlas_export_for_claude",
        "atlas_export_for_cursor",
        "atlas_export_for_codex",
        "atlas_health",
    }
    assert required.issubset(names)
    for tool in listed:
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "properties" in schema


def test_mcp_missing_repo_returns_good_error(tmp_path):
    _fresh()
    missing = tmp_path / "missing"
    res = mcp.call_tool("atlas_scan_repo", {"repo_path": str(missing)})
    assert res["ok"] is False
    assert res["code"] == "repo_not_found"
    assert str(missing) in res["repo_path"]


def test_mcp_unscanned_repo_requires_scan(tmp_path):
    _fresh()
    repo = _small_repo(tmp_path)
    res = mcp.call_tool("atlas_get_codebase_map", {"repo_path": str(repo)})
    assert res["ok"] is False
    assert res["code"] == "requires_scan"


def test_mcp_smoke_small_repo_and_context_pack(tmp_path):
    _fresh()
    repo = _small_repo(tmp_path)

    scan = mcp.call_tool("atlas_scan_repo", {"repo_path": str(repo)})
    assert scan["ok"] is True
    assert scan["scan"]["file_count"] >= 3

    code_map = mcp.call_tool("atlas_get_codebase_map", {"limit": 5})
    assert code_map["ok"] is True
    assert code_map["repo_path"] == os.path.abspath(str(repo))
    assert code_map["entry_points"] or code_map["subsystems"]

    summary = mcp.call_tool("atlas_repo_summary", {"limit": 5})
    assert summary["ok"] is True
    assert summary["repo_path"] == os.path.abspath(str(repo))

    graph = mcp.call_tool("atlas_get_dependency_graph", {"view": "module", "limit": 10})
    assert graph["ok"] is True
    assert graph["returned_nodes"] <= 10

    found = mcp.call_tool("atlas_find_file", {"query": "auth", "limit": 5})
    assert found["ok"] is True
    assert any(item["path"] == "app/auth.py" for item in found["matches"])

    relevant = mcp.call_tool("atlas_find_relevant_files", {"task": "Fix AuthStore login token handling", "max_files": 6})
    assert relevant["ok"] is True
    assert any(item["path"] == "app/auth.py" for item in relevant["recommended_files"])

    pack = mcp.call_tool(
        "atlas_build_context_pack",
        {"task": "Fix AuthStore login token handling", "max_files": 6},
    )
    assert pack["ok"] is True
    assert pack["recommended_files"]
    assert any(item["path"] == "app/auth.py" for item in pack["recommended_files"])
    assert "markdown" not in pack
    assert "snippet" not in json.dumps(pack).lower()

    impact = mcp.call_tool("atlas_what_breaks", {"target": "app/auth.py"})
    assert "ok" in impact

    plan = mcp.call_tool("atlas_plan_change", {"request": "Fix AuthStore login token handling"})
    assert "ok" in plan

    plan_alias = mcp.call_tool("atlas_get_change_plan", {"task": "Fix AuthStore login token handling"})
    assert "ok" in plan_alias

    health = mcp.call_tool("atlas_repo_health", {})
    assert health["ok"] is True
    assert health["scan"]["file_count"] >= 3

    mcp_health = mcp.call_tool("atlas_health", {})
    assert mcp_health["ok"] is True
    assert "atlas_export_for_codex" in [tool["name"] for tool in mcp.list_tools()["tools"]]

    export = mcp.call_tool("atlas_export_for_codex", {"task": "Fix AuthStore login token handling", "max_files": 6})
    assert export["ok"] is True
    assert "app/auth.py" in export["selected_files"]
    assert isinstance(export["estimated_tokens"], int)
    assert "class AuthStore" not in export["text"]
    assert "snippet" not in json.dumps(export).lower()


def test_mcp_jsonrpc_tools_call_returns_json_text(tmp_path):
    _fresh()
    repo = _small_repo(tmp_path)
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "atlas_scan_repo", "arguments": {"repo_path": str(repo)}},
    }
    response = mcp.handle_jsonrpc(message)
    assert response and response["id"] == 1
    text = response["result"]["content"][0]["text"]
    payload = json.loads(text)
    assert payload["ok"] is True
