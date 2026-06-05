"""Phase 132 — Impact engine, investigation recall, and Repository Map smoke."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from jarvis_desktop import api, impact_engine  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / "static"
REF_REPO = Path(__file__).resolve().parents[2] / "benchmarks" / "repos" / "atlas_reference"


@pytest.fixture()
def ref_scan():
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None,
                       "risks": None, "evidence_store": None, "scan_cache": {}})
    res = api.scan_repository(str(REF_REPO))
    assert res.get("ok"), res
    return res


# --------------------------------------------------------------------------
# Impact engine
# --------------------------------------------------------------------------

class TestImpactEngine:
    def test_returns_full_structure(self, ref_scan):
        r = impact_engine.analyze_impact("auth/middleware.py", api._STATE)
        assert r["ok"]
        for key in ("direct_impact", "indirect_impact", "affected_files",
                    "tests_likely_affected", "risks_of_incorrect_fix",
                    "what_may_break", "what_probably_wont_break",
                    "confidence", "evidence", "recommended_verification",
                    "entry_points_affected", "runtime_flows_affected", "risk_level"):
            assert key in r, f"missing {key}"

    def test_subsystem_blast_includes_siblings(self, ref_scan):
        # Changing auth/middleware.py should surface its auth sibling login.py.
        r = impact_engine.analyze_impact("auth/middleware.py", api._STATE)
        affected = " ".join(r["affected_files"]).lower()
        assert "auth/login.py" in affected or "auth/session.py" in affected

    def test_tests_impact_found(self, ref_scan):
        r = impact_engine.analyze_impact("auth/middleware.py", api._STATE)
        tests_blob = " ".join(r["tests_likely_affected"]).lower()
        assert "auth" in tests_blob  # test_auth.py or 'auth subsystem tests'

    def test_risk_tokens_specific(self, ref_scan):
        r = impact_engine.analyze_impact("auth/middleware.py", api._STATE)
        risk_blob = " ".join(r["risks_of_incorrect_fix"]).lower()
        assert "auth" in risk_blob or "security" in risk_blob

    def test_missing_target_is_graceful(self, ref_scan):
        # Phase 161 — unresolved target returns ok=False (no fake blast radius),
        # not an ok=true mock. The failure must still be graceful (no traceback).
        r = impact_engine.analyze_impact("does/not/exist.py", api._STATE)
        assert r["ok"] is False
        assert r.get("mock") is not True
        assert r.get("status") in ("target_not_resolved", "no_graph", "target_outside_graph_scope")
        assert "Traceback" not in str(r.get("reason", ""))

    def test_change_impact_simulation_wires_engine(self, ref_scan):
        res = api.change_impact_simulation("cache/redis_client.py")
        assert res["ok"]
        assert "simulation" in res
        sim = res["simulation"]
        assert sim.get("potentially_affected_modules")
        assert "risk_level" in sim


# --------------------------------------------------------------------------
# Impact benchmark category target (>= 85)
# --------------------------------------------------------------------------

class TestImpactBenchmark:
    def test_impact_category_meets_target(self):
        from benchmarks.runner import run_suite, _aggregate
        results = run_suite(include_optional=False)
        agg = _aggregate(results)
        impact = agg["by_category"]["impact_analysis"]
        assert impact["atlas_score_mean"] >= 85.0, impact

    def test_mean_meets_target(self):
        from benchmarks.runner import run_suite, _aggregate
        results = run_suite(include_optional=False)
        agg = _aggregate(results)
        assert agg["atlas_score_mean"] >= 82.0, agg["atlas_score_mean"]


# --------------------------------------------------------------------------
# Investigation recall (inv_017 / inv_019 specifically)
# --------------------------------------------------------------------------

class TestInvestigationRecall:
    def _inv(self, ref_scan, prompt):
        return api.investigate_symptom(prompt)

    def test_migration_failure_surfaces_file(self, ref_scan):
        res = self._inv(ref_scan, "database migration fails on deploy")
        files = " ".join(res["plan"]["likely_modules"]).lower()
        assert "migration" in files

    def test_order_fill_delay_surfaces_files(self, ref_scan):
        res = self._inv(ref_scan, "orders fill slowly in paper but not backtest")
        files = " ".join(res["plan"]["likely_modules"]).lower()
        assert "execution" in files or "paper_trading" in files

    def test_risk_contains_regression(self, ref_scan):
        res = self._inv(ref_scan, "stale cache returns old data")
        risks = " ".join(res["plan"]["risks_of_incorrect_fix"]).lower()
        assert "regression" in risks


# --------------------------------------------------------------------------
# Repository Map visual smoke contract
# --------------------------------------------------------------------------

class TestRepositoryMapSmoke:
    def test_smoke_page_exists(self):
        page = STATIC / "graph_smoke.html"
        assert page.is_file()
        html = page.read_text(encoding="utf-8")
        # global THREE before 3d-force-graph
        assert "three@0.157.0" in html
        assert html.index("three.min.js") < html.index("3d-force-graph")
        # uses the opaque-sphere technique + audits mesh count
        assert "nodeThreeObject" in html
        assert "MeshBasicMaterial" in html
        assert "__SMOKE_RESULT" in html

    def test_smoke_artifact_present_and_passing(self):
        import json
        art = Path(__file__).resolve().parents[2] / "reports" / "artifacts" / "repository_map_smoke.json"
        assert art.is_file()
        data = json.loads(art.read_text(encoding="utf-8"))
        assert data["result"]["pass"] is True
        assert data["result"]["meshes"] == data["result"]["nodes"]
        assert data["result"]["minRadius"] >= 3


# --------------------------------------------------------------------------
# Impact UI contract
# --------------------------------------------------------------------------

class TestImpactUI:
    def test_impact_ui_uses_rich_engine(self):
        app = (STATIC / "app.js").read_text(encoding="utf-8")
        block = app[app.index("async function runImpact"):]
        block = block[: block.index("function impactInspect")]
        assert "/api/planning/impact" in block
        assert "Direct impact" in block
        assert "Indirect impact" in block
        assert "What may break" in block
        assert "Safe rollback" in block
