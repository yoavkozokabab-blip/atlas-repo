"""Phase 163 — hypothesis pruning to top 3 with evidence fields."""

from __future__ import annotations

from jarvis_desktop import planning_engine as pe


def _ctx(paths):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 3}
        for i, p in enumerate(paths)
    ]
    return {
        "graph": {"nodes": nodes, "edges": [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}]},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": [{"path": paths[0], "fan_in": 5, "total_score": 12}]},
        "evidence_store": {},
        "scan": {"file_count": len(paths), "module_count": len(paths), "dependency_edges": 1},
    }


def test_hypotheses_capped_at_three():
    paths = ["dispatch/event.py", "listeners/handler.py", "core/hub.py", "api/routes.py", "services/auth.py"]
    ctx = _ctx(paths)
    res = pe.investigate_symptom("duplicate events fired twice in dispatch/event.py", ctx)
    assert res["ok"]
    hyps = res["plan"]["hypotheses"]
    assert len(hyps) <= 3


def test_every_hypothesis_has_evidence_fields():
    paths = ["trading/backtest_engine.py", "trading/paper_trading.py", "broker/adapter.py"]
    ctx = _ctx(paths)
    res = pe.investigate_symptom("backtest results differ from live trading fills", ctx)
    plan = res["plan"]
    for h in plan["hypotheses"]:
        assert "confidence" in h
        assert "evidence_score_100" in h or "evidence_score" in h
        assert "evidence_reason" in h
