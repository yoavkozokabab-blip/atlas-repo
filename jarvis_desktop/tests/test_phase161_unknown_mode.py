"""Phase 161 — strict Unknown Mode: never fake certainty.

Allowed honest outputs: Unknown / Insufficient evidence / Unable to resolve target.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from jarvis_desktop import planning_engine as pe
from jarvis_desktop import api
from jarvis_desktop.impact_engine.engine import analyze_impact


def _graph(paths):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": i, "dotted": p}
        for i, p in enumerate(paths)
    ]
    return {"nodes": nodes, "edges": []}


def _empty_ctx():
    return {
        "graph": {"nodes": [], "edges": []},
        "index": {"files": []},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "empty",
        "entry_points": [],
        "scan": {},
    }


# --------------------------------------------------------------------------- #
# Task 2/3 — root cause insufficient evidence
# --------------------------------------------------------------------------- #
def test_empty_graph_root_cause_is_insufficient_evidence():
    res = pe.investigate_symptom("the login is broken", _empty_ctx())
    assert res["ok"] is True
    plan = res["plan"]
    root = (plan.get("most_likely_root_cause") or "").lower()
    assert "insufficient evidence" in root or "enough" in root, root
    assert plan.get("root_cause_evidence_score", 0) < plan.get("root_cause_threshold", 50)


def test_root_cause_has_evidence_score_0_to_100():
    res = pe.investigate_symptom("why are events fired twice", _empty_ctx())
    plan = res["plan"]
    score = plan.get("root_cause_evidence_score")
    assert isinstance(score, int)
    assert 0 <= score <= 100
    # Every hypothesis carries a 0-100 evidence score too.
    for h in plan.get("hypotheses") or []:
        assert 0 <= h.get("evidence_score_100", 0) <= 100


def test_stdlib_never_becomes_root_cause():
    ctx = {
        "graph": _graph(["__future__.py", "re.py", "api/routes.py", "services/event.py"]),
        "index": {"files": [{"path": p} for p in ["__future__.py", "re.py", "api/routes.py"]]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "r",
        "entry_points": [],
        "scan": {},
    }
    res = pe.investigate_symptom("why are events fired twice", ctx)
    root = (res["plan"].get("most_likely_root_cause") or "").lower()
    assert "__future__" not in root
    assert "`re.py`" not in root


# --------------------------------------------------------------------------- #
# Task 4 — impact: unable to resolve target (no fake success)
# --------------------------------------------------------------------------- #
def test_impact_engine_unresolved_is_ok_false():
    state = {"graph": _graph(["api/routes.py", "services/auth.py"]), "index": {"files": []}, "scan": {}}
    res = analyze_impact("does/not/exist.py", state)
    assert res["ok"] is False
    assert res.get("status") in ("target_not_resolved", "no_graph", "target_outside_graph_scope")
    assert res.get("mock") is not True


def test_impact_engine_no_graph_is_ok_false():
    res = analyze_impact("any/file.py", {"graph": None, "scan": {}})
    assert res["ok"] is False
    assert res.get("status") == "no_graph"


def test_legacy_impact_mock_is_not_success():
    """The legacy mock helper must never claim ok=true / fabricate a blast radius."""
    mock = api._impact_mock("ghost/file.py", reason="not found")
    assert mock["ok"] is False
    assert mock.get("mock") is not True
    assert mock.get("status") == "target_not_resolved"
    assert mock.get("affected_files") == []
    assert "todo" not in mock


# --------------------------------------------------------------------------- #
# Unknown-mode helper contract
# --------------------------------------------------------------------------- #
def test_insufficient_evidence_response_is_honest():
    resp = pe._insufficient_evidence_response(
        "add caching",
        reason="graph too sparse",
        checked=["file index"],
        missing=["graph modules"],
        next_steps=["scan a Python repo"],
    )
    assert resp["ok"] is True
    assert resp["insufficient_evidence"] is True
    assert resp["confidence"] == "low"
    assert "message" in resp and resp["message"]
