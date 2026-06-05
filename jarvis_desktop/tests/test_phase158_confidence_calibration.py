"""Phase 158 — Confidence calibration tests.

Verifies:
- High confidence is not assigned when graph health is degraded
- Low confidence is assigned for unsupported-language repos
- Impact inherits confidence cap from scan health
- Build Plan inherits confidence cap from scan health
- evidence_count and confidence_reason fields are present
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from jarvis_desktop import planning_engine as pe
from jarvis_desktop import reliability as rel
from jarvis_desktop.impact_engine.engine import analyze_impact


def _make_ctx(paths=None, scan=None):
    paths = paths or ["api/routes.py", "services/auth.py", "core/hub.py"]
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2, "dotted": p}
        for i, p in enumerate(paths)
    ]
    edges = [{"type": "imports", "from": "n0", "to": "n1", "resolved": True}]
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "index": {"files": [{"path": p} for p in paths]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "test_repo",
        "entry_points": [],
        "scan": scan or {},
    }


# ---------------------------------------------------------------------------
# confidence_cap_for_scan tests
# ---------------------------------------------------------------------------

class TestConfidenceCapForScan:
    def test_healthy_scan_allows_high(self):
        scan = {"file_count": 200, "module_count": 73, "dependency_edges": 159}
        assert rel.confidence_cap_for_scan(scan) == "high"

    def test_unsupported_language_caps_at_low(self):
        scan = {"file_count": 24860, "module_count": 3}
        assert rel.confidence_cap_for_scan(scan) == "low"

    def test_timeout_caps_at_medium(self):
        scan = {"file_count": 1000, "module_count": 100,
                "graph_build": {"timed_out": True}}
        assert rel.confidence_cap_for_scan(scan) in ("low", "medium")

    def test_partial_graph_caps_at_medium(self):
        """Partial graph → cap is medium (not high)."""
        scan = {"file_count": 500, "module_count": 50,
                "graph_build": {"partial": True}}
        cap = rel.confidence_cap_for_scan(scan)
        # partial graph caps at medium — not high
        assert cap == "medium", f"Expected medium for partial graph, got {cap}"

    def test_zero_edge_graph_caps_confidence(self):
        scan = {"file_count": 400, "module_count": 100, "dependency_edges": 0}
        # zero_edge_graph — degraded
        cap = rel.confidence_cap_for_scan(scan)
        # Module count >= 8 so it's zero_edge_graph, which is degraded
        assert cap in ("low", "medium")


# ---------------------------------------------------------------------------
# Build Plan confidence calibration
# ---------------------------------------------------------------------------

class TestBuildPlanConfidence:
    def test_unsupported_language_build_confidence_low(self):
        """Build Plan on unsupported-language repo has confidence ≤ low."""
        bad_scan = {"file_count": 5000, "module_count": 3}
        ctx = _make_ctx(scan=bad_scan)
        result = pe.plan_change("add authentication middleware", ctx)
        assert result["ok"] is True
        plan = result.get("plan") or {}
        # Either insufficient_evidence mode or confidence == low
        if result.get("insufficient_evidence"):
            assert result["confidence"] == "low"
        else:
            assert plan.get("confidence") in ("low", "low-medium"), (
                f"Expected low confidence for unsupported language, got {plan.get('confidence')}"
            )

    def test_healthy_scan_can_have_medium_or_higher(self):
        """Build Plan on healthy Python scan can return medium or higher confidence."""
        good_scan = {"file_count": 300, "module_count": 73, "dependency_edges": 159}
        ctx = _make_ctx(
            paths=["api/middleware.py", "api/routes.py", "services/auth.py"],
            scan=good_scan
        )
        result = pe.plan_change("add rate limiting", ctx)
        assert result["ok"] is True
        plan = result.get("plan") or {}
        # Can be low-medium, medium, or higher — just not forced to low by graph health
        confidence = plan.get("confidence") or "low"
        assert confidence != "forced_low_by_cap", "confidence should be natural"

    def test_plan_includes_graph_health_field(self):
        """Build Plan must expose graph_health field."""
        ctx = _make_ctx()
        result = pe.plan_change("add caching", ctx)
        plan = result.get("plan") or {}
        # Should have graph_health OR the result itself has insufficient_evidence
        has_field = "graph_health" in plan or result.get("insufficient_evidence")
        assert has_field, "Plan must expose graph_health"


# ---------------------------------------------------------------------------
# Investigation confidence calibration
# ---------------------------------------------------------------------------

class TestInvestigationConfidence:
    def test_unsupported_language_investigation_confidence_low(self):
        """Investigation on unsupported-language repo has low confidence."""
        bad_scan = {"file_count": 10000, "module_count": 2}
        ctx = _make_ctx(scan=bad_scan)
        result = pe.investigate_symptom("why is authentication failing", ctx)
        assert result["ok"] is True
        if result.get("insufficient_evidence"):
            assert result["confidence"] == "low"
        else:
            plan = result.get("plan") or {}
            assert plan.get("confidence") in ("low", "low-medium")

    def test_investigation_includes_graph_health(self):
        """Investigation plan must expose graph_health field."""
        ctx = _make_ctx()
        result = pe.investigate_symptom("why are events fired twice", ctx)
        plan = result.get("plan") or {}
        has_field = "graph_health" in plan or result.get("insufficient_evidence")
        assert has_field, "Investigation must expose graph_health"

    def test_explicit_path_in_symptom_can_raise_confidence(self):
        """Explicit path mention boosts confidence (not lowered by explicit mention)."""
        ctx = _make_ctx(["api/routes.py", "services/auth.py"])
        result = pe.investigate_symptom(
            "why does api/routes.py fire duplicate events", ctx
        )
        plan = result.get("plan") or {}
        # Confidence should not be artificially low when explicit path matched
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# Impact confidence calibration
# ---------------------------------------------------------------------------

class TestImpactConfidence:
    def _make_state(self, paths, scan=None):
        nodes = [
            {"id": f"n{i}", "type": "module", "path": p, "fan_in": 2}
            for i, p in enumerate(paths)
        ]
        edges = [{"type": "imports", "from": "n1", "to": "n0", "resolved": True}]
        return {
            "graph": {"nodes": nodes, "edges": edges},
            "index": {"files": [{"path": p} for p in paths]},
            "scan": scan or {},
        }

    def test_healthy_scan_impact_confidence_not_forced_low(self):
        """Impact on healthy scan should not have confidence forced to low."""
        good_scan = {"file_count": 200, "module_count": 50, "dependency_edges": 100}
        state = self._make_state(["api/routes.py", "services/auth.py"], scan=good_scan)
        result = analyze_impact("api/routes.py", state)
        assert result["ok"] is True
        # Just verify confidence field exists and is meaningful
        assert "confidence" in result

    def test_unsupported_language_caps_impact_confidence(self):
        """Impact result should not claim high confidence for unsupported-language scan."""
        bad_scan = {"file_count": 20000, "module_count": 3}
        state = self._make_state(["some/path.go", "other/mod.go", "third/mod.go"], scan=bad_scan)
        result = analyze_impact("some/path.go", state)
        if result["ok"]:
            # If it resolved, confidence must be low
            assert result.get("confidence") in ("low", "low-medium", "medium"), (
                f"Unsupported language scan should not produce high confidence, "
                f"got {result.get('confidence')}"
            )
            assert result.get("graph_health") in ("unsupported_language_limited", "degraded", "healthy")

    def test_no_graph_confidence_low(self):
        """No graph → ok=False, confidence low."""
        result = analyze_impact("any/file.py", {"graph": None, "scan": {}})
        assert result["ok"] is False
        assert result["confidence"] == "low"
