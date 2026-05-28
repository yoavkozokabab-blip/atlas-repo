"""Safe filesystem and shell-open actions."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from actions.base import BaseAction
from actions.log_utils import latest_log_file
from config import TRADING_PROJECT_ROOT
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _is_safe_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        root = TRADING_PROJECT_ROOT.resolve()
        return root in resolved.parents or resolved == root
    except OSError:
        return False


def _open_path(path: Path) -> None:
    os.startfile(str(path))  # noqa: S606 — Windows Explorer/default app


class OpenProjectFolderAction(BaseAction):
    intent = Intent.OPEN_PROJECT_FOLDER.value

    def execute(self, request: CommandRequest) -> CommandResult:
        root = TRADING_PROJECT_ROOT
        if not root.is_dir():
            return result_failed(
                Intent.OPEN_PROJECT_FOLDER,
                f"Project folder not found: {root}",
            )
        try:
            _open_path(root)
        except OSError as exc:
            return result_failed(
                Intent.OPEN_PROJECT_FOLDER,
                f"Could not open project folder: {exc}",
            )
        return result_success(
            Intent.OPEN_PROJECT_FOLDER,
            f"Opened project folder: {root}",
            data={"path": str(root)},
        )


class OpenLatestLogAction(BaseAction):
    intent = Intent.OPEN_LATEST_LOG.value

    def execute(self, request: CommandRequest) -> CommandResult:
        override = request.params.get("path")
        path = Path(override) if override else latest_log_file()
        if path is None or not path.is_file():
            return result_failed(Intent.OPEN_LATEST_LOG, "No log file found to open.")
        if not _is_safe_path(path):
            return result_failed(Intent.OPEN_LATEST_LOG, "Path is outside project root.")
        try:
            _open_path(path)
        except OSError as exc:
            return result_failed(Intent.OPEN_LATEST_LOG, f"Could not open log: {exc}")
        return result_success(
            Intent.OPEN_LATEST_LOG,
            f"Opened log: {path.name}",
            data={"path": str(path)},
        )


class OpenTerminalAction(BaseAction):
    intent = Intent.OPEN_TERMINAL.value

    def execute(self, request: CommandRequest) -> CommandResult:
        root = str(TRADING_PROJECT_ROOT.resolve())
        wt = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"))
        if wt.is_file():
            try:
                subprocess.Popen(
                    [str(wt), "-d", root],
                    shell=False,
                )
            except OSError as exc:
                return result_failed(Intent.OPEN_TERMINAL, f"Could not open terminal: {exc}")
            return result_success(
                Intent.OPEN_TERMINAL,
                f"Opened Windows Terminal at {root}",
                data={"path": root},
            )
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NoExit",
                    "-Command",
                    f"Set-Location -LiteralPath '{root}'",
                ],
                shell=False,
                cwd=root,
            )
        except OSError as exc:
            return result_failed(Intent.OPEN_TERMINAL, f"Could not open terminal: {exc}")
        return result_success(
            Intent.OPEN_TERMINAL,
            f"Opened PowerShell at {root}",
            data={"path": root},
        )
