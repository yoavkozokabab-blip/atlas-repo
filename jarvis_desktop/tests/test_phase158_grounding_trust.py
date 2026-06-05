"""Phase 158 — Grounding and trust hardening tests.

Verifies:
- EMA / trading leakage is blocked for non-trading symptoms
- Root cause from stdlib/noise modules is suppressed
- Impact returns ok=False on target-not-found (not ok=True mock=True)
- Graph health blocks healthy label for unsupported-language repos
- Confidence is capped by graph health
- Unknown mode activates for unsupported-language + no evidence
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from jarvis_desktop import planning_engine as pe
from jarvis_desktop import reliability as rel
from jarvis_desktop.impact_engine.engine import analyze_impact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_small_graph(paths=None):
    """Make a minimal dependency graph for testing."""
    paths = paths or [
        "api/routes.py",
        "services/auth.py",
        "core/hub.py",
        "workers/job_1.py",
    ]
    nodes = [
        {"id": f"n{i}", "type": "module", "path": p, "fan_in": i * 2, "dotted": p.replace("/", ".").rstrip(".py")}
        for i, p in enumerate(paths)
    ]
    edges = [
        {"type": "imports", "from": "n0", "to": "n1", "resolved": True},
        {"type": "imports", "from": "n1", "to": "n2", "resolved": True},
    ]
    return {"nodes": nodes, "edges": edges}


def _make_ctx(paths=None, scan=None):
    return {
        "graph": _make_small_graph(paths),
        "index": {"files": [{"path": p} for p in (paths or [])]},
        "risks": {"ranked_modules": []},
        "evidence_store": {},
        "repo_name": "test_repo",
        "entry_points": [],
        "explanation": "test",
        "scan": scan or {},
    }


def _make_trading_ctx():
    """Context with trading-specific module paths."""
    trading_paths = [
        "trading/strategy.py",
        "indicators/ema.py",
        "backtest/runner.py",
        "broker/adapter.py",
    ]
    return _make_ctx(trading_paths)


# ---------------------------------------------------------------------------
# P0 FIX 1 — EMA / Trading leakage
# ---------------------------------------------------------------------------

class TestTradingLeakage:
    """Trading concepts must NOT appear in non-trading repos / symptoms."""

    def test_duplicate_events_not_ema(self):
        """Duplicate events investigation must NOT route to EMA."""
        ctx = _make_ctx()
        result = pe.investigate_symptom("why are duplicate events being fired", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        dk = plan.get("domain_knowledge") or {}
        # Must not route to trading/EMA
        assert dk.get("domain") != "trading", "duplicate events routed to trading domain"
        assert dk.get("concept_id") != "ema", "duplicate events routed to EMA"
        # Should route to pub_sub or be general
        concept = dk.get("concept_id") or ""
        assert concept in ("pub_sub", "", None, "general"), (
            f"Expected pub_sub/general, got {concept}"
        )

    def test_add_rate_limiting_not_trading(self):
        """'Add rate limiting' build plan must NOT include trading concepts."""
        ctx = _make_ctx()
        result = pe.plan_change("add rate limiting", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        dk = plan.get("domain_knowledge") or {}
        assert dk.get("domain") != "trading", "rate limiting plan routed to trading"

    def test_authentication_broken_not_trading(self):
        """'Authentication is broken' investigation must NOT return trading."""
        ctx = _make_ctx(["api/auth.py", "services/session.py", "middleware/auth.py"])
        result = pe.investigate_symptom("authentication is broken", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        dk = plan.get("domain_knowledge") or {}
        assert dk.get("domain") != "trading", "auth investigation routed to trading"

    def test_websocket_duplicate_not_ema(self):
        """'Websocket events duplicate' must NOT return EMA."""
        ctx = _make_ctx(["websocket/handler.py", "core/dispatcher.py", "api/ws.py"])
        result = pe.investigate_symptom("websocket events duplicate", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        dk = plan.get("domain_knowledge") or {}
        assert dk.get("concept_id") != "ema", "websocket duplicate routed to EMA"
        assert dk.get("domain") != "trading", "websocket duplicate routed to trading"

    def test_signals_nan_in_backtest_may_use_ema(self):
        """'Signals are NaN in backtest' MAY use EMA if trading evidence exists."""
        trading_ctx = _make_trading_ctx()
        result = pe.investigate_symptom("signals are NaN in backtest", trading_ctx)
        assert result["ok"] is True
        # Should NOT error; may route to trading since repo has trading files
        # (pass if no crash — exact routing depends on catalog)

    def test_general_request_not_trading_on_non_trading_repo(self):
        """Generic 'add logging' on a non-trading repo must NOT show trading concepts."""
        ctx = _make_ctx(["api/routes.py", "services/user.py", "db/models.py"])
        result = pe.plan_change("add structured logging to API handlers", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        dk = plan.get("domain_knowledge") or {}
        assert dk.get("domain") != "trading"

    def test_trading_concept_allowed_on_trading_repo(self):
        """EMA investigation is allowed when the repo contains trading paths."""
        trading_ctx = _make_trading_ctx()
        # Should not suppress the concept when repo has trading files
        result = pe.investigate_symptom("ema calculation giving wrong values", trading_ctx)
        assert result["ok"] is True
        # Just check it doesn't error — routing should allow trading


# ---------------------------------------------------------------------------
# P0 FIX 2 — No root cause from stdlib/noise modules
# ---------------------------------------------------------------------------

class TestRootCauseEvidence:
    """Root cause must never come from __future__, re, or generic noise."""

    def test_future_not_root_cause(self):
        """__future__.annotations must not be root cause for FastAPI investigation."""
        paths = [
            "__future__.py",  # stdlib noise
            "fastapi/routing.py",
            "fastapi/applications.py",
            "starlette/routing.py",
            "fastapi/middleware/cors.py",
        ]
        ctx = _make_ctx(paths)
        result = pe.investigate_symptom(
            "duplicate events being fired when requests come in", ctx
        )
        assert result["ok"] is True
        plan = result["plan"]
        root = plan.get("most_likely_root_cause") or ""
        assert "__future__" not in root.lower(), (
            f"Root cause should not mention __future__: {root}"
        )

    def test_re_not_root_cause(self):
        """re module must not be root cause."""
        paths = ["re.py", "api/routes.py", "services/event.py", "dispatch/core.py"]
        ctx = _make_ctx(paths)
        result = pe.investigate_symptom("why are events being fired twice", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        root = plan.get("most_likely_root_cause") or ""
        assert root != "Defect originates in `re.py`", (
            "re.py should never be the root cause"
        )

    def test_insufficient_evidence_message(self):
        """When no strong evidence exists, root cause must be honest."""
        # Empty graph — nothing to match
        ctx = {
            "graph": {"nodes": [], "edges": []},
            "index": {"files": []},
            "risks": {"ranked_modules": []},
            "evidence_store": {},
            "repo_name": "empty",
            "entry_points": [],
            "scan": {},
        }
        result = pe.investigate_symptom("the login is broken", ctx)
        assert result["ok"] is True
        plan = result["plan"]
        root = plan.get("most_likely_root_cause") or ""
        # Should be honest — not a hallucinated file name
        assert "enough" in root.lower() or "not localizable" in root.lower() or "insufficient" in root.lower() or root == "", (
            f"Expected honest 'insufficient evidence' root cause, got: {root}"
        )

    def test_noisy_module_demoted(self):
        """Noisy modules must not appear in files_involved at high confidence."""
        from jarvis_desktop.planning_engine import _is_noisy_module, _root_cause_evidence_score
        assert _is_noisy_module("__future__.py") is True
        assert _is_noisy_module("/re.py") is True
        assert _is_noisy_module("/os.py") is True
        assert _is_noisy_module("fastapi/routing.py") is False
        assert _is_noisy_module("services/auth.py") is False

    def test_root_cause_evidence_score_demotes_stdlib(self):
        """Stdlib module gets negative evidence score."""
        from jarvis_desktop.planning_engine import _root_cause_evidence_score
        score, reasons = _root_cause_evidence_score(
            "__future__.py", "why events fire twice",
            risks_map={}, explicit_paths=[], scored_paths=[]
        )
        assert score < 0, f"Expected negative score for stdlib, got {score}"
        assert any("demoted" in r.lower() or "stdlib" in r.lower() for r in reasons)

    def test_real_module_gets_positive_evidence(self):
        """Real source file with keyword overlap gets positive evidence score."""
        from jarvis_desktop.planning_engine import _root_cause_evidence_score
        score, reasons = _root_cause_evidence_score(
            "services/event_dispatcher.py",
            "why are events being fired twice",
            risks_map={"services/event_dispatcher.py": {"fan_in": 8, "total_score": 30}},
            explicit_paths=[],
            scored_paths=["services/event_dispatcher.py"],
        )
        assert score > 0, f"Expected positive score for real event file, got {score}"


# ---------------------------------------------------------------------------
# P0 FIX 3 — Impact ok=False on target-not-found
# ---------------------------------------------------------------------------

class TestImpactTargetResolution:
    """Impact must return ok=False when target is not resolved."""

    def test_nonexistent_file_returns_ok_false(self):
        """Targeting a nonexistent file must return ok=False."""
        state = {
            "graph": _make_small_graph(),
            "index": {"files": []},
            "scan": {},
        }
        result = analyze_impact("nonexistent/fake_file.py", state)
        assert result["ok"] is False, (
            f"Expected ok=False for nonexistent target, got ok={result['ok']}"
        )
        assert result.get("status") in ("target_not_resolved", "no_graph", "target_outside_graph_scope"), (
            f"Expected target_not_resolved status, got {result.get('status')}"
        )

    def test_no_graph_returns_ok_false(self):
        """No graph at all must return ok=False."""
        state = {"graph": None, "index": None, "scan": {}}
        result = analyze_impact("any/file.py", state)
        assert result["ok"] is False
        assert result.get("status") == "no_graph"

    def test_existing_file_returns_ok_true(self):
        """Existing file must return ok=True with status=resolved."""
        paths = ["api/routes.py", "services/auth.py", "core/hub.py"]
        state = {
            "graph": _make_small_graph(paths),
            "index": {"files": [{"path": p} for p in paths]},
            "scan": {},
        }
        result = analyze_impact("api/routes.py", state)
        assert result["ok"] is True
        assert result.get("status") == "resolved"
        assert "mock" not in result or result.get("mock") is not True, (
            "Resolved impact must not have mock=True"
        )

    def test_target_not_found_no_mock_true(self):
        """Target-not-found must NOT have mock=True."""
        state = {"graph": _make_small_graph(), "index": None, "scan": {}}
        result = analyze_impact("not/in/graph.py", state)
        assert result.get("mock") is not True, (
            "ok=False result must not have mock=True (misleading)"
        )


# ---------------------------------------------------------------------------
# P0 FIX 4 — Graph health for unsupported languages
# ---------------------------------------------------------------------------

class TestGraphHealth:
    """Graph health must NOT be 'healthy' when files >> modules."""

    def test_kubernetes_like_scan_not_healthy(self):
        """24860 files / 3 modules → unsupported_language_limited."""
        scan = {"file_count": 24860, "module_count": 3, "dependency_edges": 0}
        label = rel.graph_health_label(scan)
        assert label != "healthy", (
            f"24860 files / 3 modules must not be 'healthy', got: {label}"
        )
        assert label == "unsupported_language_limited", (
            f"Expected unsupported_language_limited, got: {label}"
        )

    def test_kubernetes_like_scan_not_confident(self):
        """Scan with 24860 files / 3 modules must cap confidence at 'low'."""
        scan = {"file_count": 24860, "module_count": 3, "dependency_edges": 0}
        cap = rel.confidence_cap_for_scan(scan)
        assert cap == "low", f"Expected confidence cap 'low', got: {cap}"

    def test_go_repo_shallow_graph(self):
        """1200 files / 2 modules → unsupported_language_limited."""
        scan = {"file_count": 1200, "module_count": 2, "dependency_edges": 0}
        assessment = rel.classify_scan(scan)
        assert assessment["category"] == rel.UNSUPPORTED_LANGUAGE, (
            f"Expected {rel.UNSUPPORTED_LANGUAGE}, got {assessment['category']}"
        )
        assert not assessment["healthy"]
        assert assessment["degraded"]

    def test_java_empty_modules_not_healthy(self):
        """spring_boot scan with 500+ files / 0 modules → zero_module_scan (not healthy)."""
        scan = {"file_count": 600, "module_count": 0}
        assessment = rel.classify_scan(scan)
        assert not assessment["healthy"]
        assert assessment["category"] in (rel.ZERO_MODULE_SCAN, rel.EMPTY_REPO, rel.UNSUPPORTED_LANGUAGE)

    def test_python_repo_can_be_healthy(self):
        """Normal Python scan → healthy."""
        scan = {"file_count": 300, "module_count": 73, "dependency_edges": 159}
        label = rel.graph_health_label(scan)
        assert label == "healthy"
        cap = rel.confidence_cap_for_scan(scan)
        assert cap == "high"

    def test_language_limit_boundary_conditions(self):
        """Boundary: exactly at threshold is not unsupported (1000 files, 25 modules)."""
        # At the boundary — should NOT trigger
        scan_at = {"file_count": 1000, "module_count": 25, "dependency_edges": 5}
        cat = rel.classify_scan(scan_at)["category"]
        assert cat != rel.UNSUPPORTED_LANGUAGE

        # Just over the threshold
        scan_over = {"file_count": 1001, "module_count": 24, "dependency_edges": 0}
        cat2 = rel.classify_scan(scan_over)["category"]
        assert cat2 == rel.UNSUPPORTED_LANGUAGE


# ---------------------------------------------------------------------------
# P0 FIX 7 — Unknown mode / insufficient evidence
# ---------------------------------------------------------------------------

class TestUnknownMode:
    """Atlas must return an honest gap response instead of fake certainty."""

    def test_unsupported_language_plan_returns_gap(self):
        """Build Plan on unsupported-language repo with 0 matches returns gap response."""
        # Simulate a Go repo: large file count, tiny module count
        bad_scan = {"file_count": 5000, "module_count": 3}
        ctx = {
            "graph": {"nodes": [], "edges": []},  # empty graph (language not supported)
            "index": {"files": []},
            "risks": {"ranked_modules": []},
            "evidence_store": {},
            "repo_name": "kubernetes",
            "entry_points": [],
            "scan": bad_scan,
        }
        result = pe.plan_change("add rate limiting to the API", ctx)
        # Should return gap or at least have confidence=low and insufficient_evidence flag
        if result.get("insufficient_evidence"):
            assert "evidence" in result.get("message", "").lower() or "safely" in result.get("message", "").lower()
        else:
            # If not gap mode, must have low confidence
            plan = result.get("plan") or {}
            assert (plan.get("confidence") or result.get("confidence")) == "low"

    def test_insufficient_evidence_response_structure(self):
        """The _insufficient_evidence_response helper has required fields."""
        resp = pe._insufficient_evidence_response(
            "add caching",
            reason="graph too sparse",
            checked=["file index"],
            missing=["graph modules"],
            next_steps=["scan a Python repo"],
        )
        assert resp["ok"] is True
        assert resp["insufficient_evidence"] is True
        assert "message" in resp
        assert "how_to_improve" in resp
        assert "what_was_missing" in resp
        assert resp["confidence"] == "low"
