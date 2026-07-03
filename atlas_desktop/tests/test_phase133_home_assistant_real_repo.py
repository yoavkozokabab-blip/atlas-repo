"""Phase 133 — Home Assistant real-repository hardening (local-only, no network)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

HA_ROOT = Path(__file__).resolve().parents[2] / "external_repos" / "home_assistant"
SKIP_REASON = f"Home Assistant repo not found at {HA_ROOT}"


def _ha_available() -> bool:
    return HA_ROOT.is_dir() and (HA_ROOT / "homeassistant").is_dir()


pytestmark = pytest.mark.skipif(not _ha_available(), reason=SKIP_REASON)


@pytest.fixture(scope="module")
def ha_state():
    """Scan Home Assistant once for the module (slow — ~2 min)."""
    from atlas_desktop import api

    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "evidence_store": None,
            "scan_cache": {},
        }
    )
    scan = api.scan_repository(str(HA_ROOT))
    assert scan.get("ok"), scan.get("error", "scan failed")
    return {
        "scan": scan,
        "graph": api._STATE.get("graph"),
        "index": api._STATE.get("index"),
        "evidence_store": api._STATE.get("evidence_store"),
    }


def test_graph_modules_and_edges(ha_state):
    graph = ha_state["graph"] or {}
    modules = [n for n in graph.get("nodes", []) if n.get("type") == "module"]
    edges = [
        e
        for e in graph.get("edges", [])
        if e.get("type") == "imports" and e.get("resolved")
    ]
    assert len(modules) > 500, f"expected >500 modules, got {len(modules)}"
    assert len(edges) > 500, f"expected >500 import edges, got {len(edges)}"


def test_subsystem_graph_not_single_node(ha_state):
    from atlas_desktop import api

    api._STATE["graph"] = ha_state["graph"]
    api._STATE["index"] = ha_state["index"]
    api._STATE["scan"] = ha_state["scan"]
    payload = api.current_graph(view="subsystem")
    assert payload.get("ok")
    assert payload.get("node_count", 0) > 5, (
        f"subsystem view collapsed to {payload.get('node_count')} nodes; "
        f"expected many clusters, not one"
    )
    assert payload.get("link_count", 0) > 0


def _impact_paths(target: str, ha_state) -> list[str]:
    from atlas_desktop import api

    api._STATE["graph"] = ha_state["graph"]
    api._STATE["index"] = ha_state["index"]
    api._STATE["scan"] = ha_state["scan"]
    api._STATE["evidence_store"] = ha_state.get("evidence_store")
    api._STATE["path"] = str(HA_ROOT)
    res = api.change_impact_simulation(target)
    assert res.get("ok"), res.get("error", res.get("reason"))
    paths = list(res.get("affected_files") or [])
    paths.append(res.get("target") or "")
    return [p.replace("\\", "/").lower() for p in paths if p]


def test_websocket_impact_resolves(ha_state):
    paths = _impact_paths("what breaks if we remove websocket support", ha_state)
    assert any("websocket" in p for p in paths), paths[:12]


def test_event_bus_impact_resolves(ha_state):
    paths = _impact_paths("impact of changing the event bus", ha_state)
    assert any(
        "core.py" in p or "helpers/event" in p or "event" in p for p in paths
    ), paths[:12]


def test_duplicate_events_not_config_hypothesis(ha_state):
    from atlas_desktop import api

    api._STATE["graph"] = ha_state["graph"]
    api._STATE["index"] = ha_state["index"]
    api._STATE["scan"] = ha_state["scan"]
    api._STATE["evidence_store"] = ha_state.get("evidence_store")
    api._STATE["path"] = str(HA_ROOT)
    res = api.investigate_symptom("duplicate events fired twice for automations")
    assert res.get("ok")
    plan = res["plan"]
    noise = (".prettierrc", "package.json", "pyproject.toml", "eslint", "prettier")
    ranked: list[str] = []
    for hyp in plan.get("hypotheses") or []:
        ranked.extend(hyp.get("files_involved") or [])
    ranked.extend(plan.get("likely_modules") or [])
    ranked.extend(plan.get("inspect_first") or [])
    for path in ranked[:8]:
        low = path.lower()
        assert not any(n in low for n in noise), f"config noise in top paths: {path}"


def _build_inspect_paths(goal: str, ha_state) -> list[str]:
    from atlas_desktop import api

    api._STATE["graph"] = ha_state["graph"]
    api._STATE["index"] = ha_state["index"]
    api._STATE["scan"] = ha_state["scan"]
    api._STATE["evidence_store"] = ha_state.get("evidence_store")
    api._STATE["path"] = str(HA_ROOT)
    res = api.plan_change(goal)
    assert res.get("ok"), res.get("error")
    plan = res["plan"]
    paths: list[str] = []
    for key in (
        "files_to_inspect_first",
        "files_likely_to_change",
        "likely_affected_modules",
    ):
        paths.extend(plan.get(key) or [])
    dk = plan.get("domain_knowledge") or {}
    roles = dk.get("file_roles") or {}
    paths.extend(roles.get("must_inspect") or [])
    paths.extend(roles.get("likely_modify") or [])
    return [p.replace("\\", "/").lower() for p in paths if p]


def test_distributed_tracing_build_localization(ha_state):
    paths = _build_inspect_paths("add distributed tracing across request lifecycle", ha_state)
    assert any(
        any(k in p for k in ("http", "websocket", "logging", "middleware", "api", "event"))
        for p in paths
    ), paths[:12]


def test_rate_limiting_build_localization(ha_state):
    paths = _build_inspect_paths("add rate limiting on websocket and HTTP APIs", ha_state)
    assert any(
        any(k in p for k in ("http", "websocket", "auth", "api", "rate"))
        for p in paths
    ), paths[:12]
