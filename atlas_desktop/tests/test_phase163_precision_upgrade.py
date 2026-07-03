"""Phase 163 — precision upgrade integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import planning_engine as pe
from atlas_desktop.evidence_engine.evidence_builder import IMPLEMENTATION_FILES_MAX
from atlas_desktop.evidence_engine import build_evidence_store
from atlas_desktop.impact_engine.engine import analyze_impact

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"


def _ctx(paths, store_dict=None):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}] if len(nodes) > 1 else []
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": store_dict or {},
        "scan": {"file_count": len(paths), "module_count": len(paths), "dependency_edges": max(0, len(paths) - 1)},
    }


def test_implementation_files_max_five():
    assert IMPLEMENTATION_FILES_MAX == 5
    paths = [f"mod/file_{i}.py" for i in range(12)]
    ctx = _ctx(paths)
    res = pe.plan_change("add rate limiting to api routes", ctx)
    assert res["ok"]
    impl = res["plan"].get("implementation_files") or []
    assert len(impl) <= 5


def test_build_plan_files_with_why():
    paths = ["api/rate_limit.py", "api/routes.py", "middleware/tracing.py"]
    ctx = _ctx(paths)
    res = pe.plan_change("add rate limiting to the API", ctx)
    why = res["plan"].get("implementation_files_with_why") or []
    assert why
    assert all("path" in w and "why" in w for w in why)


def test_impact_evidence_panel_with_store():
    if not BENCHMARK_ROOT.is_dir():
        pytest.skip("atlas_reference benchmark repo missing")
    index = {
        "files": [
            {"path": str(p.relative_to(BENCHMARK_ROOT)).replace("\\", "/")}
            for p in BENCHMARK_ROOT.rglob("*.py")
        ]
    }
    store = build_evidence_store(str(BENCHMARK_ROOT), None, index)
    paths = ["registry/signal_registry.py", "indicators/sma.py", "api/routes.py"]
    ctx = _ctx(paths, store.to_dict())
    res = analyze_impact("registry/signal_registry.py", ctx)
    assert res.get("ok")
    panel = res.get("evidence_panel") or res.get("impact_evidence_panel") or {}
    assert panel
    assert "selected_because" in panel or "repository_evidence" in panel


def test_repository_evidence_bundle_has_panel():
    if not BENCHMARK_ROOT.is_dir():
        pytest.skip("atlas_reference benchmark repo missing")
    index = {
        "files": [
            {"path": str(p.relative_to(BENCHMARK_ROOT)).replace("\\", "/")}
            for p in BENCHMARK_ROOT.rglob("*.py")
        ]
    }
    store = build_evidence_store(str(BENCHMARK_ROOT), None, index)
    paths = ["indicators/sma.py", "registry/signal_registry.py", "api/routes.py"]
    ctx = _ctx(paths, store.to_dict())
    res = pe.plan_change("add EMA indicator with configurable period", ctx)
    assert res["ok"]
    rev = res["plan"].get("repository_evidence") or {}
    panel = rev.get("evidence_panel") or res["plan"].get("evidence_panel") or {}
    assert panel.get("matched_symbols") is not None or panel.get("selected_because")
