"""Phase 40 — productivity and operating workflows (read-only, supervised)."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, SkillPermissionLevel, action


class ProductivitySkill(BaseSkill):
    name = "productivity"
    description = "Read-only productivity: git summary, tests, workspace context, session memory."
    category = "Productivity"
    aliases = ["productivity", "workspace", "study", "assistant"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "what_am_i_doing",
                "Report active app, workspace mode, and speakable next steps.",
                examples=["what am i doing", "current workspace"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "summarize_recent_changes",
                "Git log and diff stat under project root (read-only).",
                examples=["summarize recent changes"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "show_failing_tests",
                "Run pytest -q with timeout; returns exit code and tail (no auto-fix).",
                examples=["show failing tests"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "review_latest_patch",
                "Show latest supervised task patch proposal.",
                examples=["review latest patch"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "assistant_explain",
                "Rules-based explain: failure, logs, workspace (no LLM in Phase 40).",
                examples=["explain this error", "explain this architecture"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "assistant_plan",
                "Structured plan with phases; no automatic execution.",
                examples=["make a plan", "plan a dashboard redesign"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "what_were_we_doing",
                "Restore session context from local session memory.",
                examples=["what were we doing"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "summarize_session",
                "Deterministic rollup of recent commands and errors.",
                examples=["summarize session"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
            action(
                "start_study_mode",
                "Set studying activity mode and list study workspace phrases.",
                examples=["start study mode"],
                permission=SkillPermissionLevel.READ_ONLY,
            ),
        ]
