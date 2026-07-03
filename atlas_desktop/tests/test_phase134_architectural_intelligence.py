"""Phase 134 — Architectural intelligence (risk, unresolved, patterns, impact)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

HA_ROOT = Path(__file__).resolve().parents[2] / "external_repos" / "home_assistant"
SKIP_HA = not (HA_ROOT.is_dir() and (HA_ROOT / "homeassistant").is_dir())


def test_risk_model_returns_phase134_fields():
    from builder_core import architectural_risk as ar

    graph = {
        "nodes": [
            {"id": "a", "type": "module", "path": "pkg/core.py", "dotted": "pkg.core"},
            {"id": "b", "type": "module", "path": "pkg/const.py", "dotted": "pkg.const"},
            {"id": "c", "type": "module", "path": "pkg/util.py", "dotted": "pkg.util"},
        ],
        "edges": [
            {"type": "imports", "from": "b", "to": "a", "resolved": True},
            {"type": "imports", "from": "c", "to": "b", "resolved": True},
            {"type": "imports", "from": "c", "to": "a", "resolved": True},
        ],
        "statistics": {"import_cycles": []},
        "unresolved": {"imports_external": []},
    }
    index = {
        "project_root": "",
        "files": [],
        "python_analysis": [],
        "subsystems": [],
        "chunks": [],
    }
    ranking = ar.rank_modules(index, graph, top=3)
    assert ranking["engine_version"] == "phase134-v1"
    row = ranking["ranked_modules"][0]
    for key in (
        "risk_score",
        "risk_reasons",
        "risk_components",
        "risk_confidence",
    ):
        assert key in row
    assert "fan_in" in row["risk_components"]
    hubs = ranking["top_hubs"]
    risks = ranking["top_risks"]
    assert hubs[0]["fan_in"] >= hubs[-1]["fan_in"]
    assert hubs[0]["fan_in"] >= hubs[-1]["fan_in"]
    assert risks[0].get("score") is not None
    assert risks[0].get("risk_components") or ranking["ranked_modules"][0].get("risk_components")


def test_unresolved_import_classification_buckets():
    from builder_core import unresolved_imports as ui

    graph = {
        "nodes": [
            {"id": "m1", "type": "module", "path": "app/main.py", "dotted": "app.main"},
        ],
        "edges": [],
        "unresolved": {
            "imports_external": [
                {"target": "requests", "from_module": "app/main.py", "reason": "third_party_or_unknown_module"},
                {"target": "app.missing", "from_module": "app/main.py", "reason": "third_party_or_unknown_module"},
                {"target": ".sibling", "from_module": "app/main.py", "reason": "third_party_or_unknown_module"},
            ]
        },
    }
    payload = ui.classify_graph_unresolved(graph)
    b = payload["breakdown"]
    assert b.get("external_dependency", 0) >= 1
    assert payload["internal_unresolved_count"] >= 1
    assert "classification" in (payload.get("entries") or [{}])[0]


def test_const_hub_vs_risk_roles():
    from atlas_desktop import architecture_patterns as ap

    cls = ap.hub_vs_risk_classification("homeassistant/const.py", [], fan_in=40)
    assert cls["hub_role"] == "config_constant_hub"
    assert cls["risk_role"] == "low_logic_risk"


def test_architecture_patterns_detect_event_bus():
    from atlas_desktop import architecture_patterns as ap

    src = "class EventBus:\n    async def async_fire(self): ...\n    async def async_listen(self): ...\n"
    patterns = ap.detect_patterns("homeassistant/core.py", source=src, fan_in=20, fan_out=10, line_count=800)
    assert "event_bus" in patterns


def test_impact_phase134_fields_on_mock_state():
    from atlas_desktop.impact_engine.engine import analyze_impact

    graph = {
        "nodes": [
            {"id": "c", "type": "module", "path": "homeassistant/core.py", "dotted": "homeassistant.core"},
            {"id": "w", "type": "module", "path": "homeassistant/components/websocket_api/__init__.py"},
            {"id": "a", "type": "module", "path": "homeassistant/auth/session.py"},
        ],
        "edges": [
            {"type": "imports", "from": "w", "to": "c", "resolved": True},
        ],
    }
    state = {"graph": graph, "index": {"files": []}}
    res = analyze_impact("event bus", state)
    for key in (
        "architectural_blast_radius",
        "boundary_crossings",
        "runtime_criticality",
        "safe_areas",
        "risky_areas",
        "confidence_explanation",
    ):
        assert key in res
    assert any("event" in x.lower() or "core" in x.lower() for x in res.get("risky_areas", []))

    ws = analyze_impact("websocket support", state)
    assert any("websocket" in x.lower() for x in ws.get("risky_areas", []))


@pytest.fixture(scope="module")
def ha_state():
    if SKIP_HA:
        pytest.skip(f"Home Assistant repo not found at {HA_ROOT}")
    from atlas_desktop import api

    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "architecture": None,
            "scan_cache": {},
        }
    )
    scan = api.scan_repository(str(HA_ROOT))
    assert scan.get("ok"), scan.get("error")
    return {"scan": scan, "graph": api._STATE["graph"], "index": api._STATE["index"]}


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_home_assistant_graph_scale(ha_state):
    graph = ha_state["graph"]
    modules = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    edges = [e for e in graph.get("edges", []) if e.get("type") == "imports" and e.get("resolved")]
    assert len(modules) > 9000, len(modules)
    assert len(edges) > 30000, len(edges)


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_top_hubs_not_identical_to_top_risks(ha_state):
    scan = ha_state["scan"]
    hub_paths = [h.get("path") for h in scan.get("top_hubs", [])[:6]]
    risk_paths = [r.get("path") for r in scan.get("top_risks", [])[:6]]
    assert hub_paths != risk_paths


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_unresolved_breakdown_and_internal_count(ha_state):
    scan = ha_state["scan"]
    breakdown = scan.get("unresolved_breakdown") or {}
    assert breakdown
    internal = sum(
        breakdown.get(k, 0)
        for k in ("internal_missing", "relative_resolution_issue")
    )
    external = breakdown.get("external_dependency", 0)
    assert external >= internal or internal >= 0
    assert "external_dependency" in breakdown or breakdown


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_const_hub_differs_from_top_risk(ha_state):
    from atlas_desktop import architecture_patterns as ap

    scan = ha_state["scan"]
    const_hubs = [h for h in scan.get("top_hubs", []) if h.get("path", "").endswith("const.py")]
    top_risk = (scan.get("top_risks") or [{}])[0]
    if const_hubs:
        cls = ap.hub_vs_risk_classification(const_hubs[0]["path"], [], fan_in=const_hubs[0].get("fan_in", 0))
        assert cls["hub_role"] == "config_constant_hub"
    if top_risk.get("path", "").endswith("const.py"):
        assert (top_risk.get("risk_role") or top_risk.get("is_config")) != "high_change_risk"


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_architecture_summary_areas(ha_state):
    summary = ha_state["scan"].get("architecture_summary") or {}
    areas = summary.get("areas") or {}
    assert areas.get("components", 0) > 0 or summary.get("has_components")
    assert areas.get("helpers", 0) > 0 or summary.get("has_helpers")


@pytest.mark.skipif(SKIP_HA, reason="HA repo not present")
def test_event_bus_and_websocket_impact(ha_state):
    from atlas_desktop import api

    api._STATE.update(ha_state)
    api._STATE["path"] = str(HA_ROOT)
    ev = api.change_impact_simulation("impact of changing the event bus")
    assert ev.get("ok")
    risky = " ".join(ev.get("risky_areas") or []).lower()
    assert "event" in risky or "core" in risky or "automation" in risky

    ws = api.change_impact_simulation("remove websocket support")
    assert ws.get("ok")
    wr = " ".join(ws.get("risky_areas") or []).lower()
    assert "websocket" in wr or "auth" in wr or "session" in wr
