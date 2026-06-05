"""Phase 161 — confidence calibration.

Confidence is capped by evidence count, graph quality, language support, and
target resolution quality. High confidence must be rare.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from jarvis_desktop import reliability as rel
from jarvis_desktop import planning_engine as pe


HEALTHY = {"file_count": 300, "module_count": 73, "dependency_edges": 159}
K8S = {"file_count": 24860, "module_count": 3}


def _ctx(paths, scan):
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
        "repo_name": "r",
        "entry_points": [],
        "scan": scan,
    }


# --------------------------------------------------------------------------- #
# calibrate_confidence_cap matrix
# --------------------------------------------------------------------------- #
def test_zero_evidence_caps_low():
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=0, resolution="resolved") == "low"


def test_single_evidence_caps_medium():
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=1, resolution="resolved") == "medium"


def test_two_evidence_healthy_resolved_allows_high():
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=2, resolution="resolved") == "high"


def test_unresolved_resolution_caps_low():
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=5, resolution="unresolved") == "low"


def test_partial_resolution_caps_medium():
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=5, resolution="partial") == "medium"


def test_unsupported_language_caps_low_regardless_of_evidence():
    assert rel.calibrate_confidence_cap(K8S, evidence_count=10, resolution="resolved") == "low"


def test_high_requires_all_three():
    # Healthy graph + many evidence + resolved → high allowed
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=4, resolution="resolved") == "high"
    # Drop any single dimension → no longer high
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=1, resolution="resolved") != "high"
    assert rel.calibrate_confidence_cap(K8S, evidence_count=4, resolution="resolved") != "high"
    assert rel.calibrate_confidence_cap(HEALTHY, evidence_count=4, resolution="unresolved") != "high"


# --------------------------------------------------------------------------- #
# Confidence rank helper
# --------------------------------------------------------------------------- #
def test_confidence_rank_compound_labels():
    assert rel._confidence_rank("medium-high") == 2   # strongest component
    assert rel._confidence_rank("low-medium") == 1
    assert rel._confidence_rank("low") == 0
    assert rel._confidence_rank("high") == 2


# --------------------------------------------------------------------------- #
# Plan / investigate inherit the cap
# --------------------------------------------------------------------------- #
def test_plan_on_unsupported_repo_is_low_confidence():
    ctx = _ctx(["api/routes.py", "services/auth.py"], scan=K8S)
    res = pe.plan_change("add authentication middleware", ctx)
    assert res["ok"] is True
    plan = res.get("plan") or {}
    if not res.get("insufficient_evidence"):
        assert plan.get("confidence") == "low", plan.get("confidence")


def test_plan_confidence_cap_reason_present_when_capped():
    ctx = _ctx(["api/routes.py"], scan=K8S)  # 1 module + unsupported → capped
    res = pe.plan_change("add caching", ctx)
    plan = res.get("plan") or {}
    if not res.get("insufficient_evidence"):
        assert plan.get("confidence") == "low"
        assert plan.get("confidence_cap_reason")


def test_high_confidence_is_rare_across_workflows():
    """A broad battery should yield very few 'high' confidence results."""
    from jarvis_desktop import grounding_eval
    m = grounding_eval.evaluate_grounding()
    assert m["confidence_distribution"]["high_pct"] <= 25.0
