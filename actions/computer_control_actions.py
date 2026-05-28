"""Computer control actions (predefined, allowlisted)."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_blocked, result_clarification, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from computer_control.app_focus import get_focused_app
from computer_control.clipboard_actions import (
    clear_clipboard,
    copy_text_to_clipboard,
    get_clipboard_summary,
)
from computer_control.safety import (
    ComputerControlDisabledError,
    ComputerControlSafetyError,
)
from computer_control.window_actions import (
    focus_window,
    list_windows_detailed,
    maximize_window,
    minimize_window,
)


def _handle_disabled(intent: Intent) -> CommandResult:
    from config import COMPUTER_CONTROL_DISABLED_MESSAGE

    return result_blocked(intent, COMPUTER_CONTROL_DISABLED_MESSAGE)


def _handle_safety(intent: Intent, exc: Exception) -> CommandResult:
    if isinstance(exc, ComputerControlDisabledError):
        return _handle_disabled(intent)
    return result_failed(intent, str(exc), error=str(exc))


class GetFocusedAppAction(BaseAction):
    intent = Intent.GET_FOCUSED_APP.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            info = get_focused_app()
            if info.error and not info.title:
                return result_failed(Intent.GET_FOCUSED_APP, info.error, error=info.error)
            summary = f"Focused app/window: {info.title or '(untitled)'}"
            if info.minimized:
                summary += " (minimized)"
            return result_success(
                Intent.GET_FOCUSED_APP,
                summary,
                data=info.to_dict(),
            )
        except ComputerControlDisabledError as exc:
            return _handle_disabled(Intent.GET_FOCUSED_APP)
        except Exception as exc:
            return result_failed(Intent.GET_FOCUSED_APP, str(exc), error=str(exc))


class ListWindowsDetailedAction(BaseAction):
    intent = Intent.LIST_WINDOWS_DETAILED.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            windows = list_windows_detailed()
            if len(windows) == 1 and windows[0].blocked_reason and not windows[0].title:
                return result_failed(
                    Intent.LIST_WINDOWS_DETAILED,
                    windows[0].blocked_reason or "Failed to list windows",
                )
            lines = [f"Windows ({len(windows)}):"]
            for w in windows[:25]:
                flag = "eligible" if w.eligible else f"blocked:{w.blocked_reason}"
                lines.append(f"  - {w.title[:70]} ({w.width}x{w.height}, {flag})")
            return result_success(
                Intent.LIST_WINDOWS_DETAILED,
                "\n".join(lines),
                data={"windows": [w.to_dict() for w in windows]},
            )
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.LIST_WINDOWS_DETAILED)
        except Exception as exc:
            return result_failed(Intent.LIST_WINDOWS_DETAILED, str(exc), error=str(exc))


class GetClipboardSummaryAction(BaseAction):
    intent = Intent.GET_CLIPBOARD_SUMMARY.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            summary = get_clipboard_summary()
            if summary.error:
                return result_failed(
                    Intent.GET_CLIPBOARD_SUMMARY,
                    summary.error,
                    error=summary.error,
                )
            msg = f"Clipboard ({summary.length} chars"
            if summary.truncated:
                msg += ", truncated"
            msg += f"): {summary.text[:200]}"
            return result_success(
                Intent.GET_CLIPBOARD_SUMMARY,
                msg,
                data=summary.to_dict(),
            )
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.GET_CLIPBOARD_SUMMARY)
        except Exception as exc:
            return result_failed(Intent.GET_CLIPBOARD_SUMMARY, str(exc), error=str(exc))


def _window_action_result(intent: Intent, result) -> CommandResult:
    if result.ambiguous:
        return result_clarification(
            intent,
            result.message + "\nCandidates:\n" + "\n".join(f"  - {t}" for t in result.candidates),
            next_suggestions=["Use a more specific window title."],
        )
    if result.success:
        return result_success(intent, result.message, data={"matched_title": result.matched_title})
    return result_failed(intent, result.message)


class FocusWindowAction(BaseAction):
    intent = Intent.FOCUS_WINDOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        title = (request.params.get("title") or request.params.get("window") or "").strip()
        if not title:
            return result_clarification(
                Intent.FOCUS_WINDOW,
                "Specify window title, e.g. focus window Chrome",
            )
        try:
            return _window_action_result(Intent.FOCUS_WINDOW, focus_window(title))
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.FOCUS_WINDOW)
        except Exception as exc:
            return result_failed(Intent.FOCUS_WINDOW, str(exc), error=str(exc))


class CopyTextToClipboardAction(BaseAction):
    intent = Intent.COPY_TEXT_TO_CLIPBOARD.value

    def execute(self, request: CommandRequest) -> CommandResult:
        text = (request.params.get("text") or request.params.get("content") or "").strip()
        if not text:
            return result_clarification(
                Intent.COPY_TEXT_TO_CLIPBOARD,
                "Provide text to copy, e.g. copy text hello to clipboard",
            )
        try:
            summary = copy_text_to_clipboard(text)
            return result_success(
                Intent.COPY_TEXT_TO_CLIPBOARD,
                f"Copied {summary.length} characters to clipboard (redacted preview in data).",
                data=summary.to_dict(),
            )
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.COPY_TEXT_TO_CLIPBOARD)
        except ComputerControlSafetyError as exc:
            return result_blocked(Intent.COPY_TEXT_TO_CLIPBOARD, str(exc), error=str(exc))
        except Exception as exc:
            return result_failed(Intent.COPY_TEXT_TO_CLIPBOARD, str(exc), error=str(exc))


class ClearClipboardAction(BaseAction):
    intent = Intent.CLEAR_CLIPBOARD.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            summary = clear_clipboard()
            if summary.error:
                return result_failed(Intent.CLEAR_CLIPBOARD, summary.error, error=summary.error)
            return result_success(Intent.CLEAR_CLIPBOARD, "Clipboard cleared.")
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.CLEAR_CLIPBOARD)
        except Exception as exc:
            return result_failed(Intent.CLEAR_CLIPBOARD, str(exc), error=str(exc))


class MinimizeWindowAction(BaseAction):
    intent = Intent.MINIMIZE_WINDOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        title = (request.params.get("title") or request.params.get("window") or "").strip()
        if not title:
            return result_clarification(Intent.MINIMIZE_WINDOW, "Specify window title to minimize.")
        try:
            return _window_action_result(Intent.MINIMIZE_WINDOW, minimize_window(title))
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.MINIMIZE_WINDOW)
        except Exception as exc:
            return result_failed(Intent.MINIMIZE_WINDOW, str(exc), error=str(exc))


class MaximizeWindowAction(BaseAction):
    intent = Intent.MAXIMIZE_WINDOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        title = (request.params.get("title") or request.params.get("window") or "").strip()
        if not title:
            return result_clarification(Intent.MAXIMIZE_WINDOW, "Specify window title to maximize.")
        try:
            return _window_action_result(Intent.MAXIMIZE_WINDOW, maximize_window(title))
        except ComputerControlDisabledError:
            return _handle_disabled(Intent.MAXIMIZE_WINDOW)
        except Exception as exc:
            return result_failed(Intent.MAXIMIZE_WINDOW, str(exc), error=str(exc))
