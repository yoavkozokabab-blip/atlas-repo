"""Desktop operator state model (Phase 63)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class DesktopRuntimeState:
    provider: str = "local"
    safe_automation_mode: bool = True
    active_app: str = ""
    focused_window: str = ""
    open_window_count: int = 0
    last_screenshot_path: str = ""
    last_screen_summary: str = ""
    last_ocr_excerpt: str = ""
    last_action_success: bool = False
    last_exception: str = ""
    recent_actions: list[str] = field(default_factory=list)
    screen_summaries: list[str] = field(default_factory=list)
    last_updated_ts: float = field(default_factory=time.time)

    def format_debug(self) -> str:
        lines = [
            "Desktop operator state:",
            f"  provider: {self.provider}",
            f"  safe_automation_mode: {self.safe_automation_mode}",
            f"  active_app: {self.active_app or 'n/a'}",
            f"  focused_window: {self.focused_window or 'n/a'}",
            f"  open_window_count: {self.open_window_count}",
            f"  last_screenshot_path: {self.last_screenshot_path or 'n/a'}",
            f"  last_action_success: {self.last_action_success}",
            f"  last_exception: {self.last_exception or 'none'}",
            f"  recent_actions: {len(self.recent_actions)}",
        ]
        for item in self.recent_actions[-5:]:
            lines.append(f"    - {item[:140]}")
        return "\n".join(lines)
