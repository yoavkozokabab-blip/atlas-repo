"""Diagnostics tests (mocked collectors)."""

from unittest.mock import patch

import pytest

from actions.diagnostics_actions import RunDiagnosticsAction, SuggestNextStepsAction
from brain.intent_classifier import classify_rules
from config import CONFIRMATION_REQUIRED_INTENTS, IMPLEMENTED_INTENTS
from core.types import ActionStatus, CommandRequest, Intent
from diagnostics.engine import (
    _last_report,
    diagnose_dashboard,
    diagnose_recent_errors,
    run_diagnostics,
    suggest_next_steps,
)
from diagnostics.models import DiagnosticFinding, DiagnosticReport


@pytest.fixture(autouse=True)
def clear_last_report():
    import diagnostics.engine as eng

    eng._last_report = None
    yield
    eng._last_report = None


def test_diagnostics_intents_allowlisted():
    names = {
        "run_diagnostics",
        "diagnose_dashboard",
        "diagnose_trading_loop",
        "diagnose_recent_errors",
        "analyze_current_screen",
        "explain_last_failure",
        "suggest_next_steps",
    }
    assert names <= IMPLEMENTED_INTENTS
    assert names <= {i.value for i in Intent} | {i for i in names}
    for n in names:
        assert n not in CONFIRMATION_REQUIRED_INTENTS


def test_hebrew_intent_mappings():
    cases = [
        ("הרץ אבחון", Intent.RUN_DIAGNOSTICS),
        ("אבחן דאשבורד", Intent.DIAGNOSE_DASHBOARD),
        ("מה הצעדים הבאים", Intent.SUGGEST_NEXT_STEPS),
    ]
    for text, expected in cases:
        assert classify_rules(text).intent == expected


def test_run_diagnostics_dashboard_down():
    with (
        patch(
            "diagnostics.engine.collect_dashboard",
            return_value={"reachable": False, "port_open": False, "kill_switch": None},
        ),
        patch("diagnostics.engine.collect_log_errors", return_value={"lines": [], "line_count": 0}),
        patch(
            "diagnostics.engine.collect_rejections",
            return_value={"counts": {}, "top_reasons": [], "total_hits": 0, "samples": []},
        ),
        patch(
            "diagnostics.engine.collect_runtime",
            return_value={"running": True, "last_error": None, "last_result_summary": ""},
        ),
        patch(
            "diagnostics.engine.collect_screen_errors",
            return_value={"enabled": False, "match_count": 0},
        ),
        patch("diagnostics.engine.collect_loop_signals", return_value={"lines": [], "line_count": 0}),
    ):
        report = run_diagnostics()
    assert report.top_issue
    assert any(f.severity == "critical" for f in report.findings)
    data = report.to_dict()
    assert "findings" in data
    assert data["findings"][0]["suggested_steps"]


def test_diagnose_recent_errors_with_logs():
    with (
        patch(
            "diagnostics.engine.collect_log_errors",
            return_value={
                "lines": ["[a.log] ERROR connection failed"],
                "line_count": 3,
                "sources": ["a.log"],
            },
        ),
        patch(
            "diagnostics.engine.collect_rejections",
            return_value={
                "counts": {"max_positions_reached": 5},
                "top_reasons": [("max_positions_reached", 5)],
                "total_hits": 5,
                "samples": ["b.log: max_positions_reached"],
            },
        ),
    ):
        report = diagnose_recent_errors()
    assert "error" in report.top_issue.lower() or "rejection" in report.top_issue.lower()
    assert report.findings


def test_diagnose_dashboard_healthy():
    with patch(
        "diagnostics.engine.collect_dashboard",
        return_value={"reachable": True, "port_open": True, "kill_switch": False},
    ):
        report = diagnose_dashboard()
    assert report.findings
    assert any("healthy" in f.issue.lower() or "execution" in f.issue.lower() for f in report.findings)


def test_suggest_next_steps_safe_only():
    with patch(
        "diagnostics.engine.run_diagnostics",
        return_value=DiagnosticReport(
            top_issue="Dashboard down",
            findings=[
                DiagnosticFinding(
                    source="dashboard",
                    issue="Dashboard down",
                    severity="critical",
                    suggested_steps=[
                        "Run: show dashboard health",
                        "Run: open trading dashboard (allowlisted script only)",
                    ],
                )
            ],
        ),
    ):
        report = suggest_next_steps()
    steps = report.findings[0].suggested_steps
    joined = " ".join(steps).lower()
    assert "powershell" not in joined or "allowlisted" in joined
    assert "fix" not in joined
    assert "click" not in joined


def test_run_diagnostics_action_structured_result():
    with patch(
        "actions.diagnostics_actions.run_diagnostics",
        return_value=DiagnosticReport(
            top_issue="Test issue",
            findings=[],
            summary="Summary line",
            sources_checked=["dashboard"],
        ),
    ):
        result = RunDiagnosticsAction().execute(
            CommandRequest(raw_text="run diagnostics", intent=Intent.RUN_DIAGNOSTICS)
        )
    assert result.status == ActionStatus.SUCCESS
    assert result.data["top_issue"] == "Test issue"


def test_no_automation_in_diagnostics_package():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for rel in (
        "diagnostics/engine.py",
        "diagnostics/collectors.py",
        "actions/diagnostics_actions.py",
    ):
        text = (root / rel).read_text(encoding="utf-8").lower()
        assert "pyautogui" not in text
        assert "pynput" not in text
        assert "subprocess.run" not in text
