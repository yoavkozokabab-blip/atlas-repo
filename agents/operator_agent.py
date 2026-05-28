"""Operator Agent — browser, desktop, applications (Phase 70 facade)."""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.OPERATOR

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Operator Agent",
    owns=(
        "browser automation",
        "desktop vision and control",
        "application launcher",
        "website launcher",
        "computer control (gated)",
        "screen understanding",
    ),
    runtime_modules=(
        "browser/runtime.py",
        "browser/task_planner.py",
        "desktop/vision_runtime.py",
        "desktop/control_runtime.py",
        "apps/launcher.py",
        "websites/launcher.py",
        "computer_control/",
        "actions/phase62_browser_actions.py",
        "actions/phase63_desktop_actions.py",
        "actions/app_actions.py",
        "actions/website_actions.py",
    ),
)


class OperatorAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def browser_state(self):
        from browser.runtime import get_browser_runtime_state

        return get_browser_runtime_state()

    def open_browser(self, url: str = "about:blank") -> str:
        from browser.runtime import open_browser

        return open_browser(url)

    def search_web(self, query: str) -> str:
        from browser.runtime import search_web

        return search_web(query)

    def capture_screen(self) -> tuple[bool, str, str]:
        from desktop.vision_runtime import capture_active_monitor

        return capture_active_monitor()

    def what_is_on_screen(self) -> str:
        from desktop.vision_runtime import what_is_on_my_screen

        return what_is_on_my_screen()

    def recover_browser(self) -> tuple[bool, str]:
        from browser.runtime import recover_browser_session

        return recover_browser_session()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry

        return ActionRegistry().execute(request)


_operator_agent: OperatorAgent | None = None


def get_operator_agent() -> OperatorAgent:
    global _operator_agent
    if _operator_agent is None:
        _operator_agent = OperatorAgent()
    return _operator_agent
