"""System status and local environment."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, action


class SystemSkill(BaseSkill):
    name = "system"
    description = "CPU/RAM/disk/network and safe local tools."
    category = "System"
    aliases = ["system", "מחשב", "מערכת", "pc"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "show_runtime_status",
                "Voice, TTS, wake word, overlay config and active session flags.",
                examples=["show runtime status", "runtime status", "מצב ריצה"],
            ),
            action(
                "show_system_status",
                "Combined CPU, RAM, disk, and network summary.",
                examples=["מה מצב המחשב", "system status"],
            ),
            action(
                "show_disk_usage",
                "Disk usage per volume.",
                examples=["שימוש בדיסק", "disk usage"],
            ),
            action(
                "show_network_status",
                "Hostname and IPv4 addresses.",
                examples=["מצב רשת", "network status"],
            ),
            action(
                "open_terminal",
                "Open terminal in project root (no arbitrary commands).",
                examples=["פתח טרמינל", "open terminal"],
            ),
            action(
                "open_cursor",
                "Launch Cursor IDE.",
                examples=["פתח קרסור", "open cursor"],
            ),
            action(
                "open_chrome",
                "Launch Chrome browser.",
                examples=["פתח כרום", "open chrome"],
            ),
            action(
                "shutdown_jarvis",
                "Exit JARVIS (requires confirmation).",
                examples=["shutdown jarvis", "סגור את ג'רוויס"],
            ),
        ]
