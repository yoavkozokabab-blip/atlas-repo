"""Phase 131 — Precision engine validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas_desktop.evidence_engine.precision_engine import rank_files
from atlas_desktop.evidence_engine.implementation_detector import DetectionResult, detect_ema
from atlas_desktop.evidence_engine import EvidenceStore, build_evidence_store, analyze_concept
from atlas_desktop import api

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks"


def test_precision_tiers_cap_file_count():
    from atlas_desktop.evidence_engine.precision_engine import TIER1_MAX, TIER2_MAX

    detection = DetectionResult(
        concept_id="test",
        matched_symbols=[],
        search_patterns=["indicator"],
        insertion_patterns=("registry", "indicator"),
    )
    precision = rank_files(
        _FakeIndex(),
        _FakeCallGraph(),
        detection,
        heuristic_paths=[f"mod/file_{i}.py" for i in range(20)],
        insertion_path="mod/file_0.py",
    )
    assert len(precision.tier1) <= TIER1_MAX
    assert len(precision.tier1) + len(precision.tier2) <= TIER2_MAX


class _FakeIndex:
    @property
    def symbol_index(self):
        return self

    def symbols_in_file(self, path: str):
        return []


class _FakeCallGraph:
    callees = {}

    def who_depends_on_file(self, path: str):
        return []


def test_insertion_confidence_range():
    repo = BENCHMARK_ROOT / "repos" / "atlas_reference"
    if not repo.is_dir():
        pytest.skip("benchmark repo missing")
    store = build_evidence_store(str(repo), None, None)
    bundle, precision = analyze_concept(
        store,
        concept_id="ema",
        concept_name="EMA",
        category="indicator",
        domain="trading",
        path_keywords=["ema", "indicator", "registry"],
    )
    assert 0 <= precision.insertion_confidence <= 100
    assert bundle.insertion_confidence == precision.insertion_confidence
    assert "tier1_strong_evidence" in bundle.recommendation_tiers


def test_build_plan_fewer_recommendations():
    repo = BENCHMARK_ROOT / "repos" / "atlas_reference"
    if not repo.is_dir():
        pytest.skip("benchmark repo missing")
    api._STATE.update({"scan": None, "graph": None, "index": None, "risks": None, "evidence_store": None, "scan_cache": {}})
    api.scan_repository(str(repo))
    res = api.plan_change("add EMA indicator with configurable period")
    assert res["ok"]
    plan = res["plan"]
    assert len(plan.get("files_to_inspect_first") or []) <= 5
    assert len(plan.get("likely_affected_modules") or []) <= 10
    assert plan.get("insertion_confidence", 0) >= 40
    assert plan.get("recommendation_tiers")


def test_benchmark_precision_improved():
    """Phase 131 gate — precision up, recall preserved, mean score > 75."""
    results_path = BENCHMARK_ROOT / "results" / "latest_run.json"
    if not results_path.is_file():
        from benchmarks.runner import run_suite, _aggregate
        import benchmarks.runner as br

        results = run_suite(include_optional=False)
        aggregate = _aggregate(results)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps({"aggregate": aggregate, "results": [r.to_dict() for r in results]}),
            encoding="utf-8",
        )
    else:
        from benchmarks.runner import run_suite, _aggregate

        results = run_suite(include_optional=False)
        aggregate = _aggregate(results)

    assert aggregate["atlas_score_mean"] >= 75.0, aggregate
    feat = aggregate["by_category"]["feature_addition"]
    assert feat["file_precision_mean"] >= 0.35, feat
    assert feat["file_recall_mean"] >= 0.85, feat

    ema = next(r for r in results if r.scenario.scenario_id == "feat_001_ema")
    assert ema.metrics.insertion_point_correct
    assert ema.metrics.file_recall >= 0.66

    cb = next(r for r in results if r.scenario.scenario_id == "feat_004_circuit_breaker")
    assert cb.metrics.atlas_score >= ema.metrics.atlas_score - 15

    trace = next(r for r in results if r.scenario.scenario_id == "feat_005_distributed_tracing")
    assert trace.metrics.file_recall >= 0.5

    impact = [r for r in results if r.scenario.category == "impact_analysis"]
    assert sum(r.metrics.atlas_score for r in impact) / len(impact) >= 55
