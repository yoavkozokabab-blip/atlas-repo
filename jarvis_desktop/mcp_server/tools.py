"""Compatibility wrapper for Atlas MCP tool metadata and dispatch."""

from __future__ import annotations

from typing import Any, Dict

from .runtime import TOOLS, call_tool, list_tools


def _handler(name: str):
    def run(arguments: Dict[str, Any]) -> Dict[str, Any]:
        return call_tool(name, arguments)

    return run


TOOLS_BY_NAME = {tool["name"]: {**tool, "handler": _handler(tool["name"])} for tool in TOOLS}

__all__ = ["TOOLS", "TOOLS_BY_NAME", "call_tool", "list_tools"]
