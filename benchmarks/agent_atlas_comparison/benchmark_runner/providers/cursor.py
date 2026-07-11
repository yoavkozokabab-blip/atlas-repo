"""Cursor provider.

Cursor is expected to be manual unless CURSOR_BENCH_COMMAND_JSON is configured.
"""

from __future__ import annotations

from .base import Provider


class CursorProvider(Provider):
    name = "cursor"
    command_env_json = "CURSOR_BENCH_COMMAND_JSON"
    command_env = "CURSOR_BENCH_COMMAND"
