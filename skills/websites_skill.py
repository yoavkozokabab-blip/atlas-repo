"""Safe allowlisted website launcher (read-only list, open via browser)."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, SkillPermissionLevel, action


class WebsitesSkill(BaseSkill):
    name = "websites"
    description = "Open allowlisted https websites in the default browser (no automation)."
    category = "Websites"
    aliases = ["websites", "sites", "אתרים", "אתר"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "list_websites",
                "List built-in and user-approved websites.",
                examples=["list websites", "רשימת אתרים"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "open_website",
                "Open a built-in or approved website (webbrowser.open only).",
                examples=[
                    "open chatgpt",
                    "open youtube",
                    "פתח יוטיוב",
                ],
                optional_params=["website"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "approve_website",
                "Approve a catalog website or validated https URL for future opens.",
                examples=["approve website example"],
                optional_params=["website", "url"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "forget_website",
                "Remove a user-approved website (not built-ins).",
                examples=["forget website example"],
                optional_params=["website"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
        ]
