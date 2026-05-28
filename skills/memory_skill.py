"""Memory, preferences, and aliases (explicit user commands)."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, action


class MemorySkill(BaseSkill):
    name = "memory"
    description = "Remember preferences/facts, aliases, and recall stored context (no auto-memory)."
    category = "Memory"
    aliases = ["memory", "זיכרון", "זכור", "remember"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "remember_preference",
                "Store a user preference (explicit command only).",
                examples=["זכור שאני מעדיף פקודות בעברית"],
            ),
            action(
                "remember_fact",
                "Store a safe fact (explicit command only).",
                examples=["זכור שהפרויקט הראשי שלי הוא C:\\FINAL_ALGO_TRADER"],
            ),
            action(
                "list_memory",
                "List stored memory entries.",
                examples=["תראה מה אתה זוכר", "list memory"],
            ),
            action(
                "search_memory",
                "Search memory by keyword.",
                examples=["חפש בזיכרון risk"],
                optional_params=["query"],
            ),
            action(
                "show_memory_graph",
                "Show read-only links between memory, tags, projects, files, and keywords.",
                examples=["show memory graph"],
            ),
            action(
                "search_memory_graph",
                "Search the derived memory graph without executing actions.",
                examples=["search memory graph router"],
                optional_params=["query"],
            ),
            action(
                "set_alias",
                "Map phrase → allowlisted intent (confirmation still applies).",
                examples=["קבע alias: פתח מסחר = open_trading_dashboard"],
                optional_params=["alias", "intent"],
            ),
            action(
                "list_aliases",
                "List command aliases.",
                examples=["תראה aliases"],
            ),
            action(
                "delete_alias",
                "Remove an alias.",
                examples=["שכח alias פתח מסחר"],
                optional_params=["alias"],
            ),
            action(
                "forget_memory",
                "Delete a memory entry or preference by key.",
                examples=["שכח את זה"],
                optional_params=["key"],
            ),
            action(
                "list_preferences",
                "List preferences file.",
                examples=["list preferences"],
            ),
        ]
