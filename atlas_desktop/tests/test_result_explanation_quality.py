"""Result explanation quality — structured reports for workflow outputs."""
from __future__ import annotations

from atlas_desktop import planning_engine, result_reports


def _sample_change_plan():
    return {
        "goal": "Add structured logging to API handlers",
        "intent": "add",
        "confidence": "medium",
        "risk_level": "medium",
        "estimated_change_size": "Small",
        "implementation_order": ["api/handlers.py", "core/logging.py"],
        "files_to_inspect_first": ["api/handlers.py"],
        "files_likely_to_change": ["api/handlers.py", "core/logging.py"],
        "likely_affected_subsystems": ["api"],
        "verification_plan": ["Run API integration tests in tests/test_api.py"],
        "dependencies_involved": {
            "inbound_importers": ["services/billing.py"],
            "outbound_imports": ["core/logging.py"],
        },
        "repository_evidence": {
            "found": ["logging pattern in core/logging.py"],
            "file_evidences": [
                {
                    "path": "api/handlers.py",
                    "matching_symbols": ["handle_request"],
                    "selected_because": "Primary API entry for request handling.",
                    "evidence_score": 72,
                }
            ],
        },
        "implementation_files_with_why": [
            {"path": "api/handlers.py", "why": "Contains request handlers.", "tier": "implementation"},
        ],
    }


def _sample_investigation_plan():
    return {
        "symptom": "live paper fills diverge from backtest",
        "symptom_summary": "Live paper fills diverge from backtest",
        "confidence": "medium",
        "most_likely_root_cause": "Fill price logic may differ between live and backtest paths.",
        "hypotheses": [
            {
                "title": "Execution path mismatch",
                "confidence": "medium",
                "why_it_fits": "Live and backtest share symbols but may use different fee logic.",
                "files_involved": ["services/live_paper_engine.py"],
                "evidence": ["Symbol live_paper_engine referenced in symptom area"],
            }
        ],
        "verification_checklist": [
            "Compare fill timestamps in services/live_paper_engine.py against backtest runner output.",
        ],
    }


def _sample_impact_result():
    return {
        "ok": True,
        "target": "services/live_paper_engine.py",
        "confidence": "medium",
        "risk_level": "high",
        "direct_impact": ["ui/dashboard.py"],
        "indirect_impact": ["reports/pnl.py"],
        "affected_subsystems": ["execution", "ui"],
        "evidence": ["1 direct importer(s) in production graph"],
        "recommended_verification": ["Run tests covering ui/dashboard.py after changes."],
        "confidence_explanation": "1 direct importer resolved in graph",
    }


def test_debug_formatted_includes_executive_summary_and_confidence():
    plan = _sample_investigation_plan()
    md = planning_engine.format_investigation_plan_markdown(plan, user_request=plan["symptom"])
    assert "## Executive Summary" in md
    assert "**Confidence:** Medium" in md
    assert "**Evidence strength:**" in md


def test_debug_formatted_includes_ranked_files_with_reasons():
    plan = _sample_investigation_plan()
    md = planning_engine.format_investigation_plan_markdown(plan, user_request=plan["symptom"])
    assert "## Ranked files" in md
    assert "services/live_paper_engine.py" in md
    assert "Why:" in md
    assert "Risk:" in md
    assert "Action:" in md


def test_change_plan_includes_implementation_strategy():
    plan = _sample_change_plan()
    md = planning_engine.format_change_plan_markdown(plan, user_request=plan["goal"])
    assert "## Recommended implementation direction" in md
    assert "**Strategy:**" in md
    assert "api/handlers.py" in md
    assert "**Safest first change:**" in md


def test_what_breaks_includes_affected_systems_and_evidence():
    result = _sample_impact_result()
    md = result_reports.format_impact_markdown(result, user_request=result["target"])
    assert "## Impact summary" in md
    assert "**Most affected systems:**" in md
    assert "execution" in md
    assert "## Evidence" in md
    assert "direct importer" in md.lower()


def test_copy_prompt_includes_goal_files_and_verification():
    plan = _sample_change_plan()
    report = result_reports.build_change_plan_report(plan, user_request=plan["goal"])
    prompt = report["copy_prompt"]
    assert "Use the following Atlas findings" in prompt
    assert "## Goal" in prompt
    assert "## Likely files" in prompt
    assert "api/handlers.py" in prompt
    assert "## Verification steps" in prompt
    assert "## Constraints" in prompt


def test_beginner_raw_files_order_pattern_not_in_formatted_output():
    plan = _sample_change_plan()
    md = planning_engine.format_change_plan_markdown(plan, user_request=plan["goal"])
    assert "Files\n" not in md  # raw FILES section label from old beginner card
    assert "Order\n" not in md
    assert "## Ranked files" in md
    assert "CHANGE PLAN" in md
    assert "Goal:" not in md.split("Executive Summary")[1][:200]  # no bare Goal: header in summary block


def test_report_api_shape_for_all_workflows():
    change = result_reports.build_change_plan_report(_sample_change_plan(), user_request="add logging")
    debug = result_reports.build_investigation_report(_sample_investigation_plan(), user_request="fills wrong")
    impact = result_reports.build_impact_report(_sample_impact_result(), user_request="services/live_paper_engine.py")
    for report in (change, debug, impact):
        assert report.get("executive_summary")
        assert report.get("confidence", {}).get("level")
        assert isinstance(report.get("ranked_files"), list)
        assert report.get("copy_prompt")
