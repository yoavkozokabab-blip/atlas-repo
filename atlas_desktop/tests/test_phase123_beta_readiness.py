"""Phase 123 — Beta readiness sweep.

Covers the senior-engineer investigation engine (ranked hypotheses), the
build-plan rollback/what-may-break additions, the native-sphere graph
rendering contract, and the structured UI rendering.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from atlas_desktop import api, planning_engine, server


STATIC = Path(__file__).resolve().parents[1] / "static"

pytestmark = pytest.mark.usefixtures("local_guest_account")


def _universe_js() -> str:
    return (STATIC / "universe.js").read_text(encoding="utf-8")


def _app_js() -> str:
    return (STATIC / "app.js").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _demo_loaded():
    server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    yield


# --------------------------------------------------------------------------
# Part 2 — Investigation engine (ranked hypotheses)
# --------------------------------------------------------------------------

class TestInvestigationEngine:
    HYP_FIELDS = [
        "title", "confidence", "why_it_fits", "evidence", "files_involved",
        "what_to_inspect", "what_should_be_true_if_correct", "how_to_disprove",
    ]

    def _investigate(self, symptom):
        _, r = server.dispatch("POST", "/api/planning/investigate", {"symptom": symptom})
        return r

    def test_returns_senior_structure(self):
        r = self._investigate("dashboard PnL is wrong after live trades")
        assert r["ok"]
        p = r["plan"]
        for field in ("symptom_summary", "most_likely_root_cause", "hypotheses",
                      "verification_checklist", "minimal_fix_strategy", "risks_of_incorrect_fix"):
            assert field in p, f"missing investigation field: {field}"

    def test_hypotheses_are_ranked_and_complete(self):
        r = self._investigate("unexpected stop loss triggered")
        hyps = r["plan"]["hypotheses"]
        assert len(hyps) >= 2
        for h in hyps:
            for field in self.HYP_FIELDS:
                assert field in h, f"hypothesis missing {field}"
        # Confidence is ranked non-increasing
        order = {"high": 3, "medium": 2, "low": 1}
        scores = [order.get(h["confidence"], 0) for h in hyps]
        assert scores == sorted(scores, reverse=True)

    def test_stop_loss_intent_detected(self):
        r = self._investigate("price wicked and my stop loss got hit unexpectedly")
        assert r["plan"]["intent"] == "stop_loss"

    def test_position_sizing_intent_detected(self):
        r = self._investigate("position sizing is wrong, lot size too big")
        assert r["plan"]["intent"] == "position_sizing"

    def test_signal_not_triggering_intent_detected(self):
        r = self._investigate("my entry signal is not triggering on the breakout")
        assert r["plan"]["intent"] == "signal_not_triggering"

    def test_verification_checklist_nonempty(self):
        r = self._investigate("delayed telegram alerts")
        assert len(r["plan"]["verification_checklist"]) >= 1

    def test_minimal_fix_strategy_nonempty(self):
        r = self._investigate("backtest is better than paper trading")
        assert len(r["plan"]["minimal_fix_strategy"]) >= 1

    def test_markdown_has_all_sections(self):
        r = self._investigate("dashboard numbers are wrong")
        md = r["formatted"]
        # RC-1 result format (fb391aae): evidence-first sections + agent handoff.
        for section in ("## Executive Summary", "## Most likely cause",
                        "## Evidence", "## Ranked files",
                        "## Verification steps",
                        "## Next prompt for Claude / Cursor / Codex"):
            assert section in md, f"markdown missing: {section}"

    def test_claude_prompt_includes_hypotheses(self):
        r = self._investigate("unexpected stop loss")
        claude = r["prompts"]["claude"]
        # RC-1 prompt format: goal + likely files + evidence + verification.
        assert "## Most likely cause" in claude
        assert "## Evidence" in claude
        assert "## Verification steps" in claude

    def test_empty_symptom_fails_gracefully(self):
        _, r = server.dispatch("POST", "/api/planning/investigate", {"symptom": ""})
        assert not r["ok"]
        assert "Traceback" not in (r.get("error") or "")


# --------------------------------------------------------------------------
# Part 3 — Build plan (rollback + what may break)
# --------------------------------------------------------------------------

class TestBuildPlan:
    def _plan(self, request):
        _, r = server.dispatch("POST", "/api/planning/change", {"request": request})
        return r

    def test_rollback_plan_present(self):
        r = self._plan("Add Stripe billing")
        assert r["ok"]
        assert len(r["plan"]["rollback_plan"]) >= 2

    def test_what_may_break_alias_present(self):
        r = self._plan("Add user authentication")
        assert "what_may_break" in r["plan"]
        assert "affected_systems" in r["plan"]
        assert "tests_required" in r["plan"]

    def test_billing_rollback_mentions_feature_flag(self):
        r = self._plan("Add Stripe billing")
        rollback = " ".join(r["plan"]["rollback_plan"]).lower()
        assert "flag" in rollback or "sandbox" in rollback

    def test_change_markdown_has_rollback(self):
        # RC-1 markdown is an agent handoff; the rollback plan stays in the
        # structured payload (asserted above) and verification covers rollback.
        r = self._plan("Add Redis caching")
        assert "## Verification steps" in r["formatted"]
        assert len(r["plan"]["rollback_plan"]) >= 2

    def test_ten_point_fields_present(self):
        r = self._plan("Add dark mode")
        p = r["plan"]
        for field in ("affected_systems", "entry_points", "files_to_inspect_first",
                      "implementation_order", "tests_required", "risk_level",
                      "what_may_break", "rollback_plan", "confidence", "limitations"):
            assert field in p, f"build plan missing: {field}"


# --------------------------------------------------------------------------
# Part 4/5 — Graph rendering contract (native spheres, bounds-aware)
# --------------------------------------------------------------------------

class TestGraphRendering:
    def test_native_sphere_path(self):
        js = _universe_js()
        # Phase 124 — opaque custom-mesh spheres (the actual fix for invisible nodes).
        assert "nodeThreeObject(n => makeNodeMesh(n))" in js
        assert "MeshBasicMaterial" in js
        assert "buildNodeSizing" in js
        assert "computeSpatialBounds" in js

    def test_no_capped_tiny_radius_path(self):
        # The old custom-mesh branch (nodeThreeObject sphere) must not be the
        # active node-object path in buildGraph.
        js = _universe_js()
        build = js[js.find("function buildGraph"): js.find("function getBlastState")]
        assert "nodeThreeObject(n => sphereNodeObject" not in build

    def test_sizing_scales_with_bounds(self):
        js = _universe_js()
        # maxR derived from bounds (spread) so nodes are a visible fraction of the scene
        assert "bounds /" in js

    def test_risk_and_cycle_coloring_present(self):
        js = _universe_js()
        assert "in_cycle" in js
        assert "riskPercentiles" in js

    def test_app_renders_hypothesis_cards(self):
        app = _app_js()
        assert "renderHypotheses" in app
        assert "hyp-card" in app

    def test_app_has_investigate_file_action(self):
        app = _app_js()
        assert "investigateFile" in app


# --------------------------------------------------------------------------
# Part 1 — IA / routes consistency
# --------------------------------------------------------------------------

class TestInformationArchitecture:
    def test_planning_routes_registered(self):
        for path in ("/api/planning/change", "/api/planning/investigate", "/api/planning/impact"):
            assert server.route_is_registered("POST", path)

    def test_planning_impact_returns_simulation(self, monkeypatch):
        monkeypatch.setattr(server, "_account_gate_failure", lambda: None)
        assert api.load_demo_mode("medium")["ok"]
        _, c = server.dispatch("POST", "/api/planning/change", {"request": "Add caching"})
        target = (c["plan"].get("files_to_inspect_first") or ["services/auth.py"])[0]
        _, i = server.dispatch("POST", "/api/planning/impact", {"target": target})
        assert i["ok"], i
        assert "simulation" in i

    def test_nav_has_build_and_investigate(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        assert 'data-view="build"' in html
        assert 'data-view="investigate"' in html

    def test_no_repository_scanned_planning_is_graceful(self):
        api._STATE["scan"] = None
        api._STATE["graph"] = None
        api._STATE["index"] = None
        _, r = server.dispatch("POST", "/api/planning/change", {"request": "Add auth"})
        assert "ok" in r
        if not r["ok"]:
            assert "Traceback" not in (r.get("error") or "")
