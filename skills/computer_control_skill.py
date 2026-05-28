"""Computer control skill (predefined UI actions)."""

from __future__ import annotations

from skills.base import BaseSkill, SkillPermissionLevel, action


class ComputerControlSkill(BaseSkill):
    name = "computer_control"
    description = "Predefined window focus and clipboard actions (no mouse/keyboard automation)."
    category = "Computer control"
    aliases = ["computer", "window", "clipboard", "פוקוס", "קליפבורד"]

    def build_actions(self) -> list:
        return [
            action(
                "get_focused_app",
                "Read focused window title (read-only).",
                examples=["איזה אפליקציה בפוקוס", "get focused app"],
            ),
            action(
                "list_windows_detailed",
                "List windows with size/eligibility flags.",
                examples=["תראה חלונות מפורט", "list windows detailed"],
            ),
            action(
                "get_clipboard_summary",
                "Read clipboard with redaction and length cap.",
                examples=["מה יש בקליפבורד", "get clipboard summary"],
            ),
            action(
                "focus_window",
                "Focus window by title match (confirmation required).",
                examples=["תעביר פוקוס לכרום", "focus window chrome"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "copy_text_to_clipboard",
                "Copy allowlisted text to clipboard (blocks secrets).",
                examples=["העתק hello to clipboard"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "clear_clipboard",
                "Clear clipboard contents (confirmation required).",
                examples=["נקה קליפבורד", "clear clipboard"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "minimize_window",
                "Minimize window by title (confirmation required).",
                examples=["מזער חלון", "minimize window notepad"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "maximize_window",
                "Maximize window by title (confirmation required).",
                examples=["הגדל חלון", "maximize window"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
        ]
