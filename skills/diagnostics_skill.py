"""Diagnostics and cross-source analysis skill."""

from __future__ import annotations

from skills.base import BaseSkill, action


class DiagnosticsSkill(BaseSkill):
    name = "diagnostics"
    description = (
        "Read-only correlation of dashboard, logs, screen, runtime, and rejections."
    )
    category = "Diagnostics"
    aliases = ["diagnostics", "אבחון", "diagnose", "debug"]

    def build_actions(self) -> list:
        return [
            action(
                "run_diagnostics",
                "Full cross-source diagnostic scan.",
                examples=["run diagnostics", "הרץ אבחון"],
            ),
            action(
                "diagnose_dashboard",
                "Dashboard reachability and kill-switch signals.",
                examples=["diagnose dashboard", "אבחן דאשבורד"],
            ),
            action(
                "diagnose_trading_loop",
                "Loop-related log and dashboard correlation.",
                examples=["diagnose trading loop", "אבחן לופ מסחר"],
            ),
            action(
                "diagnose_recent_errors",
                "Recent log errors and rejection spikes.",
                examples=["diagnose recent errors", "אבחן שגיאות אחרונות"],
            ),
            action(
                "analyze_current_screen",
                "Screen OCR errors plus runtime context.",
                examples=["analyze current screen", "נתח מסך נוכחי"],
            ),
            action(
                "explain_last_failure",
                "Explain last JARVIS error with log context.",
                examples=["explain last failure", "הסבר כשלון אחרון"],
            ),
            action(
                "suggest_next_steps",
                "Safe read-only next steps from diagnostics.",
                examples=["suggest next steps", "מה הצעדים הבאים"],
            ),
        ]
