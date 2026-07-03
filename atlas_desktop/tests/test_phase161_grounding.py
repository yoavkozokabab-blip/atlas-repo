"""Phase 161 — grounding hardening: no concept leakage, tiered build plans, metrics."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from atlas_desktop import planning_engine as pe
from atlas_desktop import grounding_eval


def _ctx(paths, scan=None):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2,
         "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}] if len(nodes) > 1 else []
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "repo",
        "entry_points": [],
        "scan": scan or {"file_count": len(paths), "module_count": len(paths),
                         "dependency_edges": max(0, len(paths) - 1)},
    }


WEB = ["api/routes.py", "services/auth.py", "core/hub.py", "dispatch/event.py", "db/models.py"]


# --------------------------------------------------------------------------- #
# Task 1 — kill concept leakage
# --------------------------------------------------------------------------- #
LEAK_BUILD = [
    "add structured logging to API handlers",
    "add rate limiting to the API",
    "add an indicator signal pipeline",   # tempting EMA bait — must NOT inject EMA
    "add caching to the service layer",
]
LEAK_INVESTIGATE = [
    "why are duplicate events being fired",
    "authentication is broken",
    "memory leak in the worker",
    "schema validation is failing",
]


@pytest.mark.parametrize("prompt", LEAK_BUILD)
def test_no_trading_leakage_build(prompt):
    res = pe.plan_change(prompt, _ctx(WEB))
    assert res["ok"] is True
    dk = (res["plan"].get("domain_knowledge") or {})
    assert dk.get("domain") != "trading", f"trading leaked for: {prompt}"
    assert dk.get("concept_id") != "ema", f"EMA leaked for: {prompt}"


@pytest.mark.parametrize("prompt", LEAK_INVESTIGATE)
def test_no_trading_leakage_investigate(prompt):
    res = pe.investigate_symptom(prompt, _ctx(WEB))
    assert res["ok"] is True
    dk = (res["plan"].get("domain_knowledge") or {})
    assert dk.get("domain") != "trading", f"trading leaked for: {prompt}"
    assert dk.get("concept_id") != "ema", f"EMA leaked for: {prompt}"


def test_indicator_pipeline_does_not_inject_ema_without_evidence():
    """An 'indicator signal pipeline' request on a non-trading repo must not become EMA."""
    res = pe.plan_change("add an indicator signal pipeline", _ctx(WEB))
    plan = res["plan"]
    dk = plan.get("domain_knowledge") or {}
    assert dk.get("concept_id") != "ema"
    rev = plan.get("repository_evidence") or {}
    assert rev.get("concept_id") != "ema"


def test_explicit_ema_allowed_with_trading_evidence():
    """EMA is allowed when the user asks AND the repo has trading files."""
    trading = ["trading/strategy.py", "indicators/ema.py", "backtest/engine.py"]
    res = pe.investigate_symptom("ema values are wrong in backtest", _ctx(trading))
    assert res["ok"] is True  # must not crash; routing may use trading


# --------------------------------------------------------------------------- #
# Task 7 — build plan precision tiers
# --------------------------------------------------------------------------- #
def test_build_plan_exposes_file_tiers():
    res = pe.plan_change("add rate limiting to the API", _ctx(WEB))
    plan = res["plan"]
    assert "file_tiers" in plan
    tiers = plan["file_tiers"]
    assert "tier1_implementation" in tiers
    assert "tier2_review" in tiers
    assert "tier3_context" in tiers
    assert plan.get("default_tier") == "tier1_implementation"
    # Default surfaced files == tier 1 implementation files
    assert plan.get("implementation_files") == tiers["tier1_implementation"]


def test_build_plan_default_is_tier1_only():
    res = pe.plan_change("add caching", _ctx(WEB))
    plan = res["plan"]
    impl = plan.get("implementation_files") or []
    review = plan.get("review_files") or []
    # implementation files and review files are disjoint tiers
    assert not (set(impl) & set(review))


# --------------------------------------------------------------------------- #
# Task 8 — measurement thresholds
# --------------------------------------------------------------------------- #
def test_grounding_metrics_meet_thresholds():
    m = grounding_eval.evaluate_grounding()
    assert m["ok"] is True
    assert m["misleading_pct"] < 5.0, f"misleading too high: {m['misleading_pct']}%"
    assert m["wrong_pct"] < 3.0, f"wrong too high: {m['wrong_pct']}%"
    # Target resolution must be perfect on the labeled set.
    assert m["target_resolution_quality"] == 100.0


def test_high_confidence_is_rare():
    m = grounding_eval.evaluate_grounding()
    # High confidence should be the exception, not the norm.
    assert m["confidence_distribution"]["high_pct"] <= 25.0
