"""Phase 40b — productivity read-only workflows."""

from __future__ import annotations

import json
from pathlib import Path

from actions.base import BaseAction
from actions.task_actions import ShowTaskPatchAction
from config import ASSISTANT_MODE_ENABLED, COMMAND_HISTORY_PATH, PROJECT_ROOT
from core.results import result_failed, result_success
from core.session import SessionState
from core.types import CommandRequest, CommandResult, Intent
from operating.project_io import (
    read_project_file,
    run_git_summary,
    run_pytest_summary,
)
from vision.redaction import redact_sensitive_text


class ReviewLatestPatchAction(BaseAction):
    intent = Intent.REVIEW_LATEST_PATCH.value

    def execute(self, request: CommandRequest) -> CommandResult:
        result = ShowTaskPatchAction().execute(request)
        if result.intent == Intent.SHOW_TASK_PATCH:
            return result.model_copy(update={"intent": Intent.REVIEW_LATEST_PATCH})
        return result


class SummarizeRecentChangesAction(BaseAction):
    intent = Intent.SUMMARIZE_RECENT_CHANGES.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = SessionState.load()
        root = session.current_project_root or str(PROJECT_ROOT)
        summary = run_git_summary(Path(root))
        return result_success(
            Intent.SUMMARIZE_RECENT_CHANGES,
            summary,
            next_suggestions=["review latest patch", "run diagnostics", "show task queue"],
        )


class ShowFailingTestsAction(BaseAction):
    intent = Intent.SHOW_FAILING_TESTS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        session = SessionState.load()
        root = session.current_project_root or str(PROJECT_ROOT)
        summary = run_pytest_summary(Path(root))
        return result_success(
            Intent.SHOW_FAILING_TESTS,
            summary,
            next_suggestions=["explain this error", "run diagnostics", "summarize recent changes"],
        )


class SummarizeThisFileAction(BaseAction):
    intent = Intent.SUMMARIZE_THIS_FILE.value

    def execute(self, request: CommandRequest) -> CommandResult:
        session = SessionState.load()
        rel = str(request.params.get("path") or request.params.get("file") or "").strip()
        if not rel:
            rel = session.last_opened_file
            if rel:
                try:
                    rel = str(Path(rel).relative_to(session.current_project_root or PROJECT_ROOT))
                except ValueError:
                    rel = Path(rel).name
        if not rel:
            return result_failed(
                Intent.SUMMARIZE_THIS_FILE,
                "No file specified. Open a file first or say: summarize file path/to/file.py",
            )
        root = session.current_project_root or str(PROJECT_ROOT)
        text = read_project_file(rel, Path(root))
        lines = text.splitlines()
        preview = "\n".join(lines[:40])
        summary = f"File: {rel}\nLines: {len(lines)}\n\n{preview}"
        return result_success(Intent.SUMMARIZE_THIS_FILE, summary[:3500])


class ShowRecentCommandsAction(BaseAction):
    intent = Intent.SHOW_RECENT_COMMANDS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        path = Path(COMMAND_HISTORY_PATH)
        if not path.is_file():
            return result_success(Intent.SHOW_RECENT_COMMANDS, "No command history yet.")
        lines: list[str] = []
        try:
            raw_lines = path.read_text(encoding="utf-8").strip().splitlines()
            for line in raw_lines[-15:]:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                intent = entry.get("intent", "?")
                status = entry.get("status", "?")
                summary = redact_sensitive_text(str(entry.get("summary", ""))[:80])
                lines.append(f"  {intent} [{status}] — {summary}")
        except OSError as exc:
            return result_failed(Intent.SHOW_RECENT_COMMANDS, f"Could not read history: {exc}")
        body = "Recent commands (read-only):\n" + ("\n".join(lines) if lines else "  (empty)")
        return result_success(Intent.SHOW_RECENT_COMMANDS, body)


class ExplainThisErrorAction(BaseAction):
    intent = Intent.EXPLAIN_THIS_ERROR.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        if not ASSISTANT_MODE_ENABLED:
            return result_failed(
                Intent.EXPLAIN_THIS_ERROR,
                "Assistant mode disabled. Set ASSISTANT_MODE_ENABLED=true.",
            )
        from assistant.explain_rules import build_explain_report

        text = build_explain_report(focus="error")
        return result_success(
            Intent.EXPLAIN_THIS_ERROR,
            text,
            next_suggestions=["suggest next steps", "run diagnostics", "open latest log"],
        )
