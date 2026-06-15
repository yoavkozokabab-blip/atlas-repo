"""Atlas MCP server package.

Run with: ``py -m jarvis_desktop.mcp_server``.
"""

from .runtime import TOOLS, call_tool, handle_jsonrpc, list_tools, main

__all__ = ["TOOLS", "call_tool", "handle_jsonrpc", "list_tools", "main"]
