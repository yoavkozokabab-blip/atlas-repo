"""General application launch actions."""

from __future__ import annotations

import os
import subprocess

from actions.base import BaseAction
from config import CHROME_EXE, CURSOR_EXE
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _start_executable(exe: str, label: str, intent: Intent) -> CommandResult:
    path = os.path.expandvars(exe)
    if not os.path.isfile(path):
        return result_failed(
            intent,
            f"{label} not found at: {path}",
        )
    subprocess.Popen([path], shell=False)
    return result_success(intent, f"Opened {label}.")


class OpenCursorAction(BaseAction):
    intent = Intent.OPEN_CURSOR.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _start_executable(str(CURSOR_EXE), "Cursor", Intent.OPEN_CURSOR)


class OpenChromeAction(BaseAction):
    intent = Intent.OPEN_CHROME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _start_executable(str(CHROME_EXE), "Chrome", Intent.OPEN_CHROME)
