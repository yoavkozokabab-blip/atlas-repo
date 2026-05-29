"""Desktop Agent — window control, screen capture, OCR, app launcher (Sprint 3 / S3.3).

Extracted from OperatorAgent.  All execution still goes through ActionRegistry.
OperatorAgent is kept as a backward-compatible shim.
"""

from __future__ import annotations

from agents.base import AgentCapability, AgentId
from core.types import CommandRequest, CommandResult

_AGENT_ID = AgentId.DESKTOP

_CAPABILITY = AgentCapability(
    agent_id=_AGENT_ID,
    name="Desktop Agent",
    owns=(
        "window focus, minimise, maximise (confirmation-gated)",
        "screen capture and OCR (Tesseract)",
        "active window detection (win32gui)",
        "application launcher (Start Menu .lnk only, allowlisted)",
        "clipboard read/write (confirmation-gated)",
        "desktop automation: type, click (confirmation-gated)",
    ),
    runtime_modules=(
        "desktop/control_runtime.py",
        "desktop/vision_runtime.py",
        "desktop/ocr_pipeline.py",
        "vision/screen_capture.py",
        "vision/ocr.py",
        "vision/active_window.py",
        "computer_control/",
        "apps/",
        "actions/phase63_desktop_actions.py",
        "actions/computer_control_actions.py",
        "actions/vision_actions.py",
        "actions/foundation_actions.py",
        "actions/app_actions.py",
    ),
)


class DesktopAgent:
    agent_id = _AGENT_ID
    capability = _CAPABILITY

    def capture_screen(self) -> tuple[bool, str, str]:
        from desktop.vision_runtime import capture_active_monitor
        return capture_active_monitor()

    def what_is_on_screen(self) -> str:
        from desktop.vision_runtime import what_is_on_my_screen
        return what_is_on_my_screen()

    def get_active_window(self) -> dict:
        from vision.active_window import get_active_window_info
        return get_active_window_info()

    def execute_via_registry(self, request: CommandRequest) -> CommandResult:
        from actions.registry import ActionRegistry
        return ActionRegistry().execute(request)

    def health_check(self) -> bool:
        """Returns True when win32gui is importable (Windows desktop control available)."""
        try:
            import win32gui  # noqa: F401
            return True
        except ImportError:
            return False


_desktop_agent: DesktopAgent | None = None


def get_desktop_agent() -> DesktopAgent:
    global _desktop_agent
    if _desktop_agent is None:
        _desktop_agent = DesktopAgent()
    return _desktop_agent
