"""Trading project capabilities."""

from __future__ import annotations

from skills.base import BaseSkill, SkillAction, action


class TradingSkill(BaseSkill):
    name = "trading"
    description = "Trading dashboard, loops, positions, and trade analytics (read-only except confirmed loops)."
    category = "Trading"
    aliases = ["trading", "trade", "מסחר", "טריידינג", "דאשבורד"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "open_trading_dashboard",
                "Start dashboard if needed and open http://127.0.0.1:8077 in browser.",
                examples=["פתח את הדאשבורד", "open dashboard", "show dashboard"],
            ),
            action(
                "open_trading_dashboard_url",
                "Open dashboard URL in browser only (does not start server).",
                examples=["פתח כתובת דאשבורד", "open dashboard url"],
            ),
            action(
                "show_dashboard_health",
                "Check if dashboard HTTP endpoint is reachable.",
                examples=["תראה מצב הדאשבורד", "show dashboard health"],
            ),
            action(
                "run_live_daily_loop",
                "Start daily live loop script (requires confirmation).",
                examples=["תריץ לופ יומי", "run live daily loop"],
            ),
            action(
                "run_live_weekly_loop",
                "Start weekly live loop script (requires confirmation).",
                examples=["תריץ לופ שבועי", "run live weekly loop"],
            ),
            action(
                "show_open_positions",
                "Show open positions from state files.",
                examples=["תראה פוזיציות פתוחות", "show open positions"],
            ),
            action(
                "show_latest_live_report",
                "Show latest dual live report preview.",
                examples=["דוח אחרון", "latest report"],
            ),
            action(
                "show_recent_trading_history",
                "Recent trading-related log lines.",
                examples=["היסטוריית מסחר", "trading history"],
            ),
            action(
                "show_rejection_reasons",
                "Aggregate rejection/block reasons from logs.",
                examples=["תראה למה טריידים נדחו", "show rejection reasons"],
            ),
            action(
                "show_blocked_trades",
                "Show blocked/skipped/rejected trade lines.",
                examples=["תראה טריידים חסומים", "blocked trades"],
            ),
        ]


class LogsSkill(BaseSkill):
    name = "logs"
    description = "Trading log search, errors, and summarization (read-only)."
    category = "Logs"
    aliases = ["logs", "log", "לוגים", "לוג", "שגיאות"]

    def build_actions(self) -> list[SkillAction]:
        return [
            action(
                "show_last_errors",
                "Scan recent logs for error lines.",
                examples=["תראה שגיאות אחרונות", "show last errors"],
            ),
            action(
                "search_trading_logs",
                "Search recent logs for a query.",
                examples=["חפש בלוגים delayed_entry_failed", "search trading logs"],
                optional_params=["query"],
            ),
            action(
                "summarize_latest_log",
                "Summarize the newest log file.",
                examples=["תסכם את הלוג האחרון", "summarize latest log"],
            ),
            action(
                "open_latest_log",
                "Open the newest log in the default app.",
                examples=["פתח לוג אחרון", "open latest log"],
            ),
        ]
