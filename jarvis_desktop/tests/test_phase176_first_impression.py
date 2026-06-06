"""Phase 176 — first impression sprint (user perception polish)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import api, first_impression as fi
from jarvis_desktop import planning_engine

STATIC = os.path.join(os.path.dirname(__file__), "..", "static")


def _fresh() -> None:
    api._STATE.clear()
    api._STATE.update({
        "path": None, "scan": None, "graph": None, "index": None, "risks": None,
        "demo_mode": False, "last_scope": {"mode": "entire_repo"},
        "scan_cache": {}, "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        "session_export": None, "repository_memory": None, "_current_memory": None,
    })


# --- helpers ---

def test_cap_evidence_score_never_exceeds_100():
    assert fi.cap_evidence_score(150) == 100
    assert fi.cap_evidence_score(-5) == 0
    assert fi.cap_evidence_score(72.6) == 73


def test_feature_request_never_shows_implemented():
    assert fi.user_facing_implementation_status("Implemented", goal="Add structured logging") == "Proposed"
    assert fi.user_facing_implementation_status("Implemented", goal="Fix crash in hub") == "Implemented"
    assert fi.user_facing_implementation_status("Partially Implemented", goal="Add auth") == "Partially Implemented"


def test_md_optional_section_omits_empty():
    assert fi.md_optional_section("MUST inspect", []) == []
    assert "MUST inspect" in "\n".join(fi.md_optional_section("MUST inspect", ["a.py"]))


def test_format_change_plan_hides_empty_role_sections():
    plan = {
        "goal": "Add logging",
        "intent": "add",
        "domain_knowledge": {
            "applied": True,
            "concept_name": "observability",
            "concept_title": "Logging",
            "domain_label": "Platform",
            "feature_type": "cross-cutting",
            "concept_understanding": "Structured logs help ops.",
            "why_this_matters": "Debuggability.",
            "knowledge_risks": ["Ops blind spots without logs"],
            "file_roles": {
                "must_inspect": [],
                "likely_modify": [],
                "verify_only": [],
            },
        },
    }
    md = planning_engine.format_change_plan_markdown(plan)
    assert "MUST inspect:" not in md
    assert "LIKELY modify:" not in md
    assert "VERIFY only:" not in md
    for label in ("MUST inspect", "LIKELY modify", "VERIFY only"):
        assert label not in md


def test_demo_weak_response_message():
    weak = fi.demo_weak_response("build", "vague request")
    assert weak["ok"] is False
    assert "real repository" in weak["error"].lower()


# --- demo pack first-run audit ---

DEMO_FIRST_RUN = {
    "small": {
        "build": "Improve error handling in core/hub.py",
        "investigate": "API requests fail intermittently under load",
        "impact": "core/hub.py",
    },
    "medium": {
        "build": "Add structured logging to API handlers",
        "investigate": "API requests fail intermittently under load",
        "impact": "api/handlers.py",
    },
    "large": {
        "build": "Improve error handling in gateway/entry.py",
        "investigate": "API gateway returns 500 under load",
        "impact": "gateway/entry.py",
    },
}


@pytest.mark.parametrize("pack", ["small", "medium", "large"])
def test_demo_first_run_build_not_weak(pack: str):
    _fresh()
    api.load_demo_mode(pack)
    req = DEMO_FIRST_RUN[pack]["build"]
    result = api.plan_change(req)
    assert result.get("ok"), result.get("error")
    assert not fi.is_demo_unanswered("build", result)
    plan = result["plan"]
    assert plan.get("implementation_order")
    assert plan.get("confidence")


@pytest.mark.parametrize("pack", ["small", "medium", "large"])
def test_demo_first_run_investigate_not_weak(pack: str):
    _fresh()
    api.load_demo_mode(pack)
    symptom = DEMO_FIRST_RUN[pack]["investigate"]
    result = api.investigate_symptom(symptom)
    assert result.get("ok"), result.get("error")
    assert not fi.is_demo_unanswered("investigate", result)
    assert (result.get("plan") or {}).get("hypotheses")


@pytest.mark.parametrize("pack", ["small", "medium", "large"])
def test_demo_first_run_impact_not_weak(pack: str):
    _fresh()
    api.load_demo_mode(pack)
    target = DEMO_FIRST_RUN[pack]["impact"]
    result = api.change_impact_simulation(target)
    assert result.get("ok"), result.get("error")
    assert not fi.is_demo_unanswered("impact", result)
    assert result.get("direct_impact")


def test_demo_weak_returns_notice_not_empty_ok():
    _fresh()
    api.load_demo_mode("small")
    api._STATE["demo_mode"] = True
    fake = {
        "ok": True,
        "plan": {
            "confidence": "low",
            "files_to_inspect_first": [],
            "implementation_order": [],
            "repository_evidence": {"file_evidences": []},
        },
    }
    out = fi.polish_workflow_result("build", fake, api._STATE, goal="something vague")
    assert out.get("ok") is False
    assert "real repository" in (out.get("error") or "").lower()


# --- static asset checks ---

def test_investigate_placeholder_no_trading_era_copy():
    html = open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
    assert "backtest" not in html.lower()
    assert "paper trading" not in html.lower()
    assert "pnl" not in html.lower()


def test_beginner_clipboard_strip_metadata():
    js = open(os.path.join(STATIC, "atlas_zero_friction.js"), encoding="utf-8").read()
    assert "zfStripClipboardMetadata" in js
    assert "scan_signature" in js
    assert "getOutputMode" in js


def test_app_js_pack_specific_demo_examples():
    js = open(os.path.join(STATIC, "app.js"), encoding="utf-8").read()
    assert "gateway/entry.py" in js
    assert "api/handlers.py" in js
    assert "fiUserFacingStatus" in js
