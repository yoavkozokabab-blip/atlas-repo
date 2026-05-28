"""Predefined workflow skill."""

from __future__ import annotations

from skills.base import BaseSkill, action


class WorkflowsSkill(BaseSkill):
    name = "workflows"
    description = "Run predefined read-only multi-step command sequences."
    category = "Workflows"
    aliases = ["workflows", "workflow", "תהליך"]

    def build_actions(self) -> list:
        return [
            action(
                "list_workflows",
                "List predefined workflows.",
                examples=["תראה workflows", "list workflows"],
            ),
            action(
                "run_workflow",
                "Run a named workflow through the router (each step).",
                examples=["תריץ בדיקת מערכת מסחר", "run workflow trading_health_check"],
            ),
            action(
                "explain_workflow",
                "Describe workflow steps (no execution).",
                examples=["תסביר workflow מסחר", "explain workflow screen_error_check"],
            ),
        ]
