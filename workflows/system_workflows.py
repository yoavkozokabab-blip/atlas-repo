"""System / screen / code predefined workflows."""

from __future__ import annotations

from workflows.models import WorkflowDefinition, WorkflowStep


def screen_error_check() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="screen_error_check",
        title="Screen error check",
        description="Active window, on-screen errors, and screen diagnostics.",
        read_only=True,
        aliases=["בדוק שגיאות במסך", "screen errors"],
        steps=[
            WorkflowStep(
                "get_active_window",
                "get active window",
                "Focused window title and size",
            ),
            WorkflowStep(
                "detect_screen_errors",
                "detect screen errors",
                "OCR scan for error-like lines",
            ),
            WorkflowStep(
                "analyze_current_screen",
                "analyze current screen",
                "Screen + runtime diagnostic view",
            ),
        ],
    )


def code_risk_review() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="code_risk_review",
        title="Code risk review",
        description="Read-only code search for risk and execution paths.",
        read_only=True,
        aliases=["סקירת סיכון קוד", "risk review"],
        steps=[
            WorkflowStep(
                "find_risk_usage",
                "find risk usage",
                "Locate risk_per_trade and related limits",
            ),
            WorkflowStep(
                "find_delayed_entry_logic",
                "find delayed entry logic",
                "Find delayed entry handling",
            ),
            WorkflowStep(
                "find_execution_events_logic",
                "find execution events logic",
                "Find execution event / order placement logic",
            ),
        ],
    )


def jarvis_self_check() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="jarvis_self_check",
        title="JARVIS self check",
        description="System status, skills, memory, and diagnostics.",
        read_only=True,
        aliases=["בדיקת ג'רוויס", "self check"],
        steps=[
            WorkflowStep(
                "show_system_status",
                "system status",
                "CPU/RAM/disk/network summary",
            ),
            WorkflowStep(
                "list_skills",
                "list skills",
                "Registered skill groups",
            ),
            WorkflowStep(
                "list_memory",
                "list memory",
                "Safe local memory entries",
            ),
            WorkflowStep(
                "run_diagnostics",
                "run diagnostics",
                "Full cross-source diagnostics",
            ),
        ],
    )
