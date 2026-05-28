"""Phase 63 desktop operator actions."""

from __future__ import annotations

from actions.base import BaseAction
from core.results import result_clarification, result_failed, result_success
from core.types import CommandRequest, CommandResult, Intent


class WhatIsOnMyScreenAction(BaseAction):
    intent = Intent.WHAT_IS_ON_MY_SCREEN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from desktop.vision_runtime import get_desktop_state, what_is_on_my_screen

        body = what_is_on_my_screen()
        state = get_desktop_state()
        if not state.last_action_success and "disabled" in body.lower():
            return result_failed(Intent.WHAT_IS_ON_MY_SCREEN, body)
        return result_success(Intent.WHAT_IS_ON_MY_SCREEN, body, data={"read_only": True})


class SummarizeThisScreenAction(BaseAction):
    intent = Intent.SUMMARIZE_THIS_SCREEN.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from desktop.vision_runtime import summarize_this_screen

        return result_success(Intent.SUMMARIZE_THIS_SCREEN, summarize_this_screen(), data={"read_only": True})


class ClickButtonThatSaysAction(BaseAction):
    intent = Intent.CLICK_BUTTON_THAT_SAYS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from desktop.control_runtime import click_button_that_says, extract_button_label

        label = str(request.params.get("label") or "").strip() or extract_button_label(request.raw_text)
        if not label:
            return result_clarification(Intent.CLICK_BUTTON_THAT_SAYS, "Which button label should I click?")
        approved = bool(request.params.get("approved", False))
        body = click_button_that_says(label, approved=approved)
        if "Approval required" in body:
            return result_failed(Intent.CLICK_BUTTON_THAT_SAYS, body)
        return result_success(Intent.CLICK_BUTTON_THAT_SAYS, body)


class TypeThisAction(BaseAction):
    intent = Intent.TYPE_THIS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        from desktop.control_runtime import extract_type_text, type_text

        text = str(request.params.get("text") or "").strip() or extract_type_text(request.raw_text)
        if not text:
            return result_clarification(Intent.TYPE_THIS, "What text should I type?")
        approved = bool(request.params.get("approved", False))
        body = type_text(text, approved=approved)
        if "Approval required" in body:
            return result_failed(Intent.TYPE_THIS, body)
        return result_success(Intent.TYPE_THIS, body)


class SwitchToChromeAction(BaseAction):
    intent = Intent.SWITCH_TO_CHROME.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from desktop.control_runtime import switch_to_chrome

        return result_success(Intent.SWITCH_TO_CHROME, switch_to_chrome())


class ListOpenWindowsAction(BaseAction):
    intent = Intent.LIST_OPEN_WINDOWS.value

    def execute(self, request: CommandRequest) -> CommandResult:
        del request
        from desktop.vision_runtime import list_open_windows

        return result_success(Intent.LIST_OPEN_WINDOWS, list_open_windows(), data={"read_only": True})

