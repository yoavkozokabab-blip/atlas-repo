"""Read-only trading report and state actions."""

from __future__ import annotations

import json
from pathlib import Path

from actions.base import BaseAction
from config import TRADING_REPORTS_DUAL, TRADING_REPORTS_STATE
from core.results import result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


def _latest_file(directory: Path, pattern: str = "*") -> Path | None:
    if not directory.is_dir():
        return None
    files = [p for p in directory.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _read_text_preview(path: Path, max_chars: int = 4000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n... (truncated)"
    return text


class ShowLatestLiveReportAction(BaseAction):
    intent = Intent.SHOW_LATEST_LIVE_REPORT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        latest = _latest_file(TRADING_REPORTS_DUAL)
        if latest is None:
            return result_failed(
                Intent.SHOW_LATEST_LIVE_REPORT,
                f"No reports found in {TRADING_REPORTS_DUAL}",
            )
        preview = _read_text_preview(latest)
        return result_success(
            Intent.SHOW_LATEST_LIVE_REPORT,
            f"Latest report: {latest.name}\n\n{preview}",
            data={"path": str(latest)},
        )


class ShowOpenPositionsAction(BaseAction):
    intent = Intent.SHOW_OPEN_POSITIONS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if not TRADING_REPORTS_STATE.is_dir():
            return result_failed(
                Intent.SHOW_OPEN_POSITIONS,
                f"State directory not found: {TRADING_REPORTS_STATE}",
            )

        candidates = list(TRADING_REPORTS_STATE.glob("**/positions*.json"))
        candidates += list(TRADING_REPORTS_STATE.glob("**/open_positions*.json"))
        candidates += list(TRADING_REPORTS_STATE.glob("**/*.json"))

        if not candidates:
            latest = _latest_file(TRADING_REPORTS_STATE)
            if latest is None:
                return result_failed(
                    Intent.SHOW_OPEN_POSITIONS,
                    "No position state files found.",
                )
            content = _read_text_preview(latest, max_chars=6000)
            return result_success(
                Intent.SHOW_OPEN_POSITIONS,
                f"Latest state file: {latest.name}\n\n{content}",
                data={"path": str(latest)},
            )

        path = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            positions = data["positions"] if isinstance(data, dict) and "positions" in data else data
            summary = json.dumps(positions, indent=2, ensure_ascii=False)
            if len(summary) > 6000:
                summary = summary[:6000] + "\n... (truncated)"
            return result_success(
                Intent.SHOW_OPEN_POSITIONS,
                f"Open positions from {path.name}:\n\n{summary}",
                data={"path": str(path)},
            )
        except json.JSONDecodeError:
            content = _read_text_preview(path, max_chars=6000)
            return result_success(
                Intent.SHOW_OPEN_POSITIONS,
                f"State file (non-JSON): {path.name}\n\n{content}",
                data={"path": str(path)},
            )
