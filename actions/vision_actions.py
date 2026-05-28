"""Read-only vision / screen understanding actions."""

from __future__ import annotations

from actions.base import BaseAction
import config
from config import SCREEN_UNDERSTANDING_DISABLED_MESSAGE, VISION_DISABLED_MESSAGE
from core.results import result_blocked, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent
from vision.screen_analyzer import (
    describe_screen,
    detect_screen_errors,
    read_screen_text,
    take_screenshot_data,
)
from vision.screen_capture import VisionDisabledError
from vision.screen_understanding import (
    analyze_active_window_v35,
    describe_screen_v35,
    extract_find_query,
    find_on_screen_v35,
    read_screen_v35,
)
from vision.window_info import get_active_window_info, list_visible_windows


def _screen_understanding_active() -> bool:
    return bool(config.SCREEN_UNDERSTANDING_ENABLED)


def _legacy_vision_active() -> bool:
    return bool(config.VISION_ENABLED)


def _vision_blocked(intent: Intent) -> CommandResult:
    if _screen_understanding_active():
        return result_blocked(intent, SCREEN_UNDERSTANDING_DISABLED_MESSAGE)
    return result_blocked(intent, VISION_DISABLED_MESSAGE)


def _screen_blocked(intent: Intent) -> CommandResult:
    return result_blocked(intent, SCREEN_UNDERSTANDING_DISABLED_MESSAGE)


def _run_vision(intent: Intent, fn) -> CommandResult:
    if not _legacy_vision_active() and not _screen_understanding_active():
        return _vision_blocked(intent)
    try:
        data = fn()
        if data.get("disabled"):
            return _screen_blocked(intent)
        return result_success(intent, data.get("summary", "Done."), data=data)
    except VisionDisabledError:
        return _vision_blocked(intent)
    except Exception as exc:
        return result_failed(intent, f"Vision action failed: {exc}", error=str(exc))


def _run_screen_v35(intent: Intent, fn) -> CommandResult:
    if not _screen_understanding_active():
        return _screen_blocked(intent)
    try:
        data = fn()
        if data.get("disabled"):
            return _screen_blocked(intent)
        return result_success(intent, data.get("summary", "Done."), data=data)
    except Exception as exc:
        return result_failed(
            intent,
            f"Screen understanding failed: {exc}",
            error=str(exc),
        )


class DescribeScreenAction(BaseAction):
    intent = Intent.DESCRIBE_SCREEN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            import config as cfg

            if cfg.DESKTOP_OPERATOR_ENABLED and _screen_understanding_active():
                from desktop.vision_runtime import what_is_on_my_screen

                body = what_is_on_my_screen()
                if "disabled" not in body.lower():
                    return result_success(Intent.DESCRIBE_SCREEN, body, data={"read_only": True})
        except Exception:
            pass
        if _screen_understanding_active():
            return _run_screen_v35(Intent.DESCRIBE_SCREEN, describe_screen_v35)
        if not _legacy_vision_active():
            return _screen_blocked(Intent.DESCRIBE_SCREEN)
        return _run_vision(Intent.DESCRIBE_SCREEN, describe_screen)


class ReadScreenTextAction(BaseAction):
    intent = Intent.READ_SCREEN_TEXT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        if _screen_understanding_active():
            return _run_screen_v35(Intent.READ_SCREEN_TEXT, read_screen_v35)
        if not _legacy_vision_active():
            return _screen_blocked(Intent.READ_SCREEN_TEXT)
        return _run_vision(Intent.READ_SCREEN_TEXT, read_screen_text)


class AnalyzeActiveWindowAction(BaseAction):
    intent = Intent.ANALYZE_ACTIVE_WINDOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run_screen_v35(Intent.ANALYZE_ACTIVE_WINDOW, analyze_active_window_v35)


class FindOnScreenAction(BaseAction):
    intent = Intent.FIND_ON_SCREEN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        query = extract_find_query(request.raw_text, request.params)
        return _run_screen_v35(
            Intent.FIND_ON_SCREEN,
            lambda: find_on_screen_v35(query),
        )


class DetectScreenErrorsAction(BaseAction):
    intent = Intent.DETECT_SCREEN_ERRORS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        return _run_vision(Intent.DETECT_SCREEN_ERRORS, detect_screen_errors)


class GetActiveWindowAction(BaseAction):
    intent = Intent.GET_ACTIVE_WINDOW.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            win = get_active_window_info()
            if win.error and not win.title:
                return result_failed(
                    Intent.GET_ACTIVE_WINDOW,
                    f"Could not read active window: {win.error}",
                    error=win.error,
                )
            summary = (
                f"Active window: {win.title or '(untitled)'} "
                f"({win.width}x{win.height}, "
                f"{'minimized' if win.minimized else 'visible'})"
            )
            return result_success(
                Intent.GET_ACTIVE_WINDOW,
                summary,
                data=win.__dict__,
            )
        except Exception as exc:
            return result_failed(
                Intent.GET_ACTIVE_WINDOW,
                f"Window info unavailable: {exc}",
                error=str(exc),
            )


class TakeScreenshotAction(BaseAction):
    intent = Intent.TAKE_SCREENSHOT.value

    def execute(self, request: CommandRequest) -> CommandResult:
        save = bool(request.params.get("save", False))
        try:
            import config as cfg

            if cfg.DESKTOP_OPERATOR_ENABLED and _screen_understanding_active():
                from desktop.vision_runtime import take_screenshot

                body = take_screenshot()
                if "REAL DESKTOP VISION" in body or "Captured" in body:
                    return result_success(Intent.TAKE_SCREENSHOT, body, data={"save": save})
        except Exception:
            pass
        return _run_vision(
            Intent.TAKE_SCREENSHOT,
            lambda: take_screenshot_data(save=save),
        )


class ListVisibleWindowsAction(BaseAction):
    intent = Intent.LIST_VISIBLE_WINDOWS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        try:
            windows = list_visible_windows()
            if len(windows) == 1 and windows[0].error:
                return result_failed(
                    Intent.LIST_VISIBLE_WINDOWS,
                    f"Could not list windows: {windows[0].error}",
                    error=windows[0].error,
                )
            lines = []
            for w in windows:
                state = "minimized" if w.minimized else "visible"
                lines.append(f"{w.title[:70]} ({w.width}x{w.height}, {state})")
            summary = f"Visible windows ({len(lines)}):\n" + "\n".join(lines[:20])
            if len(lines) > 20:
                summary += f"\n... +{len(lines) - 20} more"
            return result_success(
                Intent.LIST_VISIBLE_WINDOWS,
                summary.strip(),
                data={"windows": [w.__dict__ for w in windows]},
            )
        except Exception as exc:
            return result_failed(
                Intent.LIST_VISIBLE_WINDOWS,
                f"Window list failed: {exc}",
                error=str(exc),
            )
