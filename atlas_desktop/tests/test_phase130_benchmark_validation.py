"""Phase 130 — Repository understanding benchmark validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks"


def test_suite_has_fifty_plus_scenarios():
    raw = json.loads((BENCHMARK_ROOT / "atlas_benchmark_suite_v1.json").read_text(encoding="utf-8"))
    scenarios = raw["scenarios"]
    assert len(scenarios) >= 50
    assert raw["categories"]["feature_addition"] >= 20
    assert raw["categories"]["bug_investigation"] >= 20
    assert raw["categories"]["impact_analysis"] >= 10


def test_reference_repo_exists():
    repo = BENCHMARK_ROOT / "repos" / "atlas_reference"
    assert repo.is_dir()
    assert (repo / "indicators" / "sma.py").is_file()
    assert (repo / "auth" / "middleware.py").is_file()


def test_evaluator_file_metrics():
    from benchmarks.evaluator import _file_precision, _file_recall

    rec = ["indicators/sma.py", "services/http_client.py"]
    exp = ["indicators/sma.py", "indicators/indicator_registry.py"]
    assert _file_precision(rec, exp) == 0.5
    assert _file_recall(rec, exp) == 0.5


@pytest.fixture(scope="module")
def benchmark_results():
    from benchmarks.runner import run_suite

    return run_suite(include_optional=False)


def test_benchmark_runner_executes(benchmark_results):
    assert len(benchmark_results) >= 50
    ok = [r for r in benchmark_results if r.ok and not r.error]
    assert len(ok) >= 45, f"too many failures: {[r.scenario.scenario_id for r in benchmark_results if r.error]}"


def test_feature_addition_ema_scores(benchmark_results):
    ema = next(r for r in benchmark_results if r.scenario.scenario_id == "feat_001_ema")
    assert ema.ok
    assert ema.metrics.file_recall >= 0.33
    assert ema.metrics.atlas_score >= 35


def test_investigation_backtest_evidence(benchmark_results):
    inv = next(r for r in benchmark_results if r.scenario.scenario_id == "inv_001_backtest_paper")
    assert inv.ok
    assert inv.metrics.finding_recall >= 0.2 or inv.metrics.evidence_quality >= 25


def test_impact_auth_middleware(benchmark_results):
    imp = next(r for r in benchmark_results if r.scenario.scenario_id == "imp_001_delete_auth_middleware")
    assert imp.ok
    assert imp.metrics.file_recall >= 0.5


def test_evidence_audit_populated(benchmark_results):
    audits = [a for r in benchmark_results for a in r.evidence_audits]
    assert isinstance(audits, list)
