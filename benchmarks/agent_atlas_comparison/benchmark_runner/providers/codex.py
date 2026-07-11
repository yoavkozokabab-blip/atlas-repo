"""Codex provider.

Set CODEX_BENCH_COMMAND_JSON to a JSON array command when a non-interactive
Codex runner is available. The prompt is sent on stdin.
"""

from __future__ import annotations

from .base import Provider


class CodexProvider(Provider):
    name = "codex"
    command_env_json = "CODEX_BENCH_COMMAND_JSON"
    command_env = "CODEX_BENCH_COMMAND"
