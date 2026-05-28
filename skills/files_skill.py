"""Filesystem helpers for the trading project."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, action


class FilesSkill(BaseSkill):
    name = "files"
    description = "Open project folders and files safely under TRADING_PROJECT_ROOT."
    category = "Files"
    aliases = ["files", "file", "קבצים", "תיקייה", "folder"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "open_project_folder",
                "Open trading project root in File Explorer.",
                examples=["פתח את התיקייה של הפרויקט", "open project folder"],
            ),
        ]
