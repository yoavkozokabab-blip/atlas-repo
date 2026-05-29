"""Browser Agent — web browsing, DOM read, URL validation (Sprint 3 / S3.2).

Extracted from OperatorAgent.  All execution still goes through ActionRegistry
(this is an ownership/routing boundary, not an execution bypass).

OperatorAgent is kept as a backward-compatible shim.
"""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.BROWSER

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Browser Agent",
    owns=(
        "browser session management (Playwright or mock)",
        "URL validation and allowlist enforcement",
        "DOM read and page summarisation",
        "web search (Google search URL)",
        "multi-step browser task planning",
        "browser action replay log",
    ),
    runtime_modules=(
        "browser/runtime.py",
        "browser/dom_read.py",
        "browser/task_planner.py",
        "browser/url_parser.py",
        "browser/memory.py",
        "actions/phase62_browser_actions.py",
        "actions/website_actions.py",
        "actions/apps.py",       # open_chrome
    ),
)


class BrowserAgent:
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

    def summarize_page(self) -> str:
        from browser.runtime import summarize_current_page
        return summarize_current_page()

    def recover_browser(self) -> tuple[bool, str]:
        from browser.runtime import recover_browser_session
        return recover_browser_session()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry
        return ActionRegistry().execute(request)

    def health_check(self) -> bool:
        """Returns True when the browser module is importable (mock or real)."""
        try:
            from browser.runtime import get_browser_runtime_state
            _ = get_browser_runtime_state()
            return True
        except Exception:
            return False


_browser_agent: BrowserAgent | None = None


def get_browser_agent() -> BrowserAgent:
    global _browser_agent
    if _browser_agent is None:
        _browser_agent = BrowserAgent()
    return _browser_agent
