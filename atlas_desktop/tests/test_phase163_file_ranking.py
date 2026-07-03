"""Phase 163 — fused path + symbol file ranking."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import planning_engine as pe
from atlas_desktop.evidence_engine import build_evidence_store
from atlas_desktop.evidence_engine.precision_engine import WEIGHT_PATH, rank_files
from atlas_desktop.evidence_engine.implementation_detector import detect_ema

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"


def _ctx_with_store(paths, store_dict):
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 1}
        for i, p in enumerate(paths)
    ]
    return {
        "graph": {"nodes": nodes, "edges": []},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": store_dict,
        "scan": {"file_count": len(paths), "module_count": len(paths), "dependency_edges": 0},
    }


def test_precision_engine_exposes_path_weight():
    assert WEIGHT_PATH > 0


def test_fused_ranking_prefers_symbol_match():
    if not BENCHMARK_ROOT.is_dir():
        pytest.skip("atlas_reference benchmark repo missing")
    paths = [
        "indicators/sma.py",
        "api/routes.py",
        "middleware/tracing.py",
    ]
    index = {
        "files": [
            {"path": str(p.relative_to(BENCHMARK_ROOT)).replace("\\", "/")}
            for p in BENCHMARK_ROOT.rglob("*.py")
        ]
    }
    store = build_evidence_store(str(BENCHMARK_ROOT), None, index)
    ctx = _ctx_with_store(paths, store.to_dict())
    modules = pe._production_modules(ctx["graph"])
    risks = pe._risks_map(ctx["risks"])
    path_only = pe._score_modules(modules, {"api"}, risks)
    fused = pe._fuse_module_scores(path_only, ctx, {"indicator", "sma"})
    top_path = fused[0][1]["path"] if fused else ""
    assert "indicator" in top_path or "registry" in top_path or "signal" in top_path


def test_rank_files_include_selected_because():
    if not BENCHMARK_ROOT.is_dir():
        pytest.skip("atlas_reference benchmark repo missing")
    index = {
        "files": [
            {"path": str(p.relative_to(BENCHMARK_ROOT)).replace("\\", "/")}
            for p in BENCHMARK_ROOT.rglob("*.py")
        ]
    }
    store = build_evidence_store(str(BENCHMARK_ROOT), None, index)
    detection = detect_ema(store.symbol_index, store.call_graph, ["ema", "indicator"])
    precision = rank_files(
        store.symbol_index,
        store.call_graph,
        detection,
        concept_keywords=["ema", "indicator"],
        insertion_path="registry/signal_registry.py",
    )
    assert precision.file_evidences
    fe = precision.file_evidences[0]
    assert fe.selected_because or fe.reason_selected
    assert fe.path_score >= 0 or fe.symbol_score >= 0
