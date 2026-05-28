"""Windows autostart and local health services."""

from __future__ import annotations

from skills.base import BaseSkill, SkillPermissionLevel, action


class ServicesSkill(BaseSkill):
    name = "services"
    description = "Windows autostart, health checks, and tray watchdog (report-only)."
    category = "Services"
    aliases = ["services", "autostart", "watchdog", "שירותים"]

    def build_actions(self) -> list:
        return [
            action(
                "enable_autostart",
                "Add Startup shortcut to run_jarvis_tray.ps1 (confirmation required).",
                examples=["תפעיל הפעלה אוטומטית", "enable autostart"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "disable_autostart",
                "Remove Startup shortcut (confirmation required).",
                examples=["תבטל הפעלה אוטומטית", "disable autostart"],
                permission=SkillPermissionLevel.CONFIRM_REQUIRED,
            ),
            action(
                "show_autostart_status",
                "Read-only autostart shortcut status.",
                examples=["מצב הפעלה אוטומטית", "show autostart status"],
            ),
            action(
                "run_jarvis_health_check",
                "Local health: voice, tray, Tesseract, Ollama, disk, logs.",
                examples=["בדוק את ג'רוויס", "run jarvis health check"],
            ),
            action(
                "show_watchdog_status",
                "Last periodic watchdog status from data/watchdog_status.json.",
                examples=["מה מצב watchdog", "show watchdog status"],
            ),
        ]
