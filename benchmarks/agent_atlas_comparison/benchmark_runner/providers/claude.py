"""Claude provider for future comparison runs."""

from __future__ import annotations

from .base import Provider


class ClaudeProvider(Provider):
    name = "claude"
    command_env_json = "CLAUDE_BENCH_COMMAND_JSON"
    command_env = "CLAUDE_BENCH_COMMAND"
