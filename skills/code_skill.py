"""Read-only code intelligence under the trading project."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, action


class CodeSkill(BaseSkill):
    name = "code"
    description = "Search code and config in FINAL_ALGO_TRADER (read-only)."
    category = "Code search"
    aliases = ["code", "קוד", "codebase", "search"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "search_project_file_by_name",
                "Find files by partial name.",
                examples=["חפש קובץ fib_quality", "search file config"],
                optional_params=["query"],
            ),
            action(
                "search_code_text",
                "Search source text for a string.",
                examples=["חפש בקוד max_positions_reached", "search code"],
                optional_params=["query"],
            ),
            action(
                "find_function",
                "Locate function definitions.",
                examples=["חפש פונקציה generate_trades", "find function"],
                optional_params=["name"],
            ),
            action(
                "find_class",
                "Locate class definitions.",
                examples=["חפש מחלקה PortfolioManager", "find class"],
                optional_params=["name"],
            ),
            action(
                "find_config_key",
                "Find configuration key usages.",
                examples=["איפה מוגדר risk_per_trade", "find config key"],
                optional_params=["key"],
            ),
            action(
                "find_risk_usage",
                "Grouped search for risk-related symbols.",
                examples=["איפה מוגדר risk per trade", "find risk usage"],
            ),
            action(
                "find_delayed_entry_logic",
                "Grouped search for delayed entry logic.",
                examples=["איפה הלוגיקה של delayed entry", "delayed entry logic"],
            ),
            action(
                "find_execution_events_logic",
                "Grouped search for execution event patterns.",
                examples=["איפה יש execution events", "execution events"],
            ),
        ]
