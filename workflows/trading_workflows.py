"""Trading-related predefined workflows."""

from __future__ import annotations

from workflows.models import WorkflowDefinition, WorkflowStep


def trading_health_check() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="trading_health_check",
        title="Trading health check",
        description=(
            "Read-only pass: dashboard health, recent errors, rejections, full diagnostics."
        ),
        read_only=True,
        aliases=["בדיקת מערכת מסחר", "trading health"],
        steps=[
            WorkflowStep(
                "show_dashboard_health",
                "show dashboard health",
                "Check dashboard reachability and status",
            ),
            WorkflowStep(
                "show_last_errors",
                "show last errors",
                "Scan recent log errors",
            ),
            WorkflowStep(
                "show_rejection_reasons",
                "show rejection reasons",
                "Aggregate rejection/block reasons",
            ),
            WorkflowStep(
                "run_diagnostics",
                "run diagnostics",
                "Cross-source diagnostic summary",
            ),
        ],
    )
