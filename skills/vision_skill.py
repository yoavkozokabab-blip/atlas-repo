"""Vision / screen understanding skill (read-only)."""

from __future__ import annotations

from skills.base import BaseSkill, action


class VisionSkill(BaseSkill):
    name = "vision"
    description = "Read-only screen capture, OCR, and window context (local only)."
    category = "Vision / Screen Understanding"
    aliases = ["vision", "screen", "מסך", "ocr"]

    def build_actions(self) -> list:
        return [
            action(
                "describe_screen",
                "Summarize active window, visible windows, and OCR preview.",
                examples=["מה יש במסך", "describe screen"],
            ),
            action(
                "read_screen_text",
                "OCR visible text with secret redaction.",
                examples=["קרא את הטקסט במסך", "read screen text"],
            ),
            action(
                "detect_screen_errors",
                "Find error-like lines in on-screen text.",
                examples=["יש שגיאה במסך", "detect screen errors"],
            ),
            action(
                "get_active_window",
                "Title and geometry of the focused window.",
                examples=["איזה חלון פתוח", "get active window"],
            ),
            action(
                "take_screenshot",
                "Capture screen (saved only if configured or save=true).",
                examples=["צלם מסך", "take screenshot"],
            ),
            action(
                "list_visible_windows",
                "List open window titles (read-only).",
                examples=["תראה חלונות פתוחים", "list visible windows"],
            ),
        ]
