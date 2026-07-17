from __future__ import annotations

import io
import json

from atlas_desktop.mcp_server import runtime


def test_malformed_and_deep_jsonrpc_are_rejected_before_tool_execution(monkeypatch):
    called = []
    monkeypatch.setattr(runtime, "call_tool", lambda *args, **kwargs: called.append(args) or {"ok": True})
    assert runtime.handle_jsonrpc("not-an-object")["error"]["code"] == -32600
    deep = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    cursor = deep
    for _ in range(runtime.MAX_JSONRPC_DEPTH + 1):
        cursor["nested"] = {}
        cursor = cursor["nested"]
    assert runtime.handle_jsonrpc(deep)["error"]["code"] == -32600
    assert runtime.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"arguments": []}})["error"]["code"] == -32600
    assert called == []


def test_stdio_limits_reject_large_messages_and_bound_responses():
    oversized = b"{" + (b"x" * runtime.MAX_JSONRPC_BYTES) + b"}\n"
    messages = list(runtime._read_messages(io.BytesIO(oversized)))
    assert messages == [{"_atlas_invalid": "JSON-RPC request too large"}]
    output = io.BytesIO()
    runtime._write_message(output, {"jsonrpc": "2.0", "id": 1, "result": "x" * runtime.MAX_JSONRPC_RESPONSE_BYTES})
    response = json.loads(output.getvalue())
    assert response["error"]["code"] == -32600
