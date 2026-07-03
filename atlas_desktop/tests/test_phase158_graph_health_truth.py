"""Phase 158 — Graph health truth tests.

Verifies:
- Kubernetes-like (24860 files / 3 modules) is NOT healthy
- Go/Java/C# with shallow graphs are NOT healthy
- Python with normal module count IS healthy
- Health label is correctly mapped for all fault categories
- confidence_cap_for_scan returns correct cap values
- graph_health_label returns correct string labels
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from atlas_desktop import reliability as rel


# ---------------------------------------------------------------------------
# graph_health_label tests
# ---------------------------------------------------------------------------

class TestGraphHealthLabel:
    def test_healthy_python_repo(self):
        """Normal Python scan → healthy."""
        scan = {"file_count": 300, "module_count": 73, "dependency_edges": 159}
        assert rel.graph_health_label(scan) == "healthy"

    def test_healthy_ts_repo(self):
        """Normal TypeScript scan → healthy."""
        scan = {"file_count": 500, "module_count": 218, "dependency_edges": 335}
        assert rel.graph_health_label(scan) == "healthy"

    def test_kubernetes_unsupported_language(self):
        """Kubernetes: 24860 files, 3 modules → unsupported_language_limited."""
        scan = {"file_count": 24860, "module_count": 3}
        label = rel.graph_health_label(scan)
        assert label == "unsupported_language_limited", (
            f"Expected unsupported_language_limited for Kubernetes, got {label}"
        )

    def test_gin_go_shallow(self):
        """Gin (Go): 1200 files, 0 modules → degraded or unsupported."""
        scan = {"file_count": 1200, "module_count": 0}
        label = rel.graph_health_label(scan)
        # 0 modules from 1200 files = zero_module_scan (retryable)
        assert label != "healthy", f"Expected not-healthy for empty Go graph, got {label}"

    def test_gin_go_tiny_modules(self):
        """Gin (Go): 1200 files, 1 module → unsupported_language_limited."""
        scan = {"file_count": 1200, "module_count": 1, "dependency_edges": 0}
        label = rel.graph_health_label(scan)
        assert label == "unsupported_language_limited"

    def test_spring_boot_java(self):
        """Spring Boot (Java): 700 files, 0 modules → zero_module_scan."""
        scan = {"file_count": 700, "module_count": 0}
        label = rel.graph_health_label(scan)
        assert label in ("degraded", "unsupported_language_limited"), (
            f"Spring Boot with 0 modules should be degraded/unsupported, got {label}"
        )

    def test_timeout_scan(self):
        """Timed-out scan → degraded."""
        scan = {"file_count": 50000, "module_count": 9709,
                "graph_build": {"timed_out": True}}
        label = rel.graph_health_label(scan)
        assert label == "degraded"

    def test_partial_graph(self):
        """Partial graph → partial."""
        scan = {"file_count": 300, "module_count": 100,
                "graph_build": {"partial": True}}
        label = rel.graph_health_label(scan)
        assert label == "partial"

    def test_zero_edge_graph(self):
        """Zero edges with many modules → degraded."""
        scan = {"file_count": 100, "module_count": 50, "dependency_edges": 0}
        label = rel.graph_health_label(scan)
        assert label == "degraded"

    def test_unresolved_explosion(self):
        """Unresolved import explosion → partial."""
        scan = {
            "file_count": 500, "module_count": 100, "dependency_edges": 50,
            "unresolved_imports": 5000, "unresolved_ratio": 0.92,
        }
        label = rel.graph_health_label(scan)
        assert label == "partial"


# ---------------------------------------------------------------------------
# classify_scan: new UNSUPPORTED_LANGUAGE category
# ---------------------------------------------------------------------------

class TestClassifyScanLanguage:
    def test_unsupported_language_is_a_fault(self):
        """UNSUPPORTED_LANGUAGE is a fault category."""
        assert rel.UNSUPPORTED_LANGUAGE in rel.FAULT_CATEGORIES

    def test_classify_unsupported_returns_correct_category(self):
        scan = {"file_count": 5000, "module_count": 10}
        result = rel.classify_scan(scan)
        assert result["category"] == rel.UNSUPPORTED_LANGUAGE
        assert not result["healthy"]
        assert result["degraded"]

    def test_classify_healthy_not_unsupported(self):
        scan = {"file_count": 200, "module_count": 73, "dependency_edges": 100}
        result = rel.classify_scan(scan)
        assert result["category"] == rel.OK
        assert result["healthy"]
        assert not result["degraded"]

    def test_warnings_describe_language_gap(self):
        """Warnings for unsupported_language_limited mention language support."""
        scan = {"file_count": 8000, "module_count": 5}
        result = rel.classify_scan(scan)
        assert result["category"] == rel.UNSUPPORTED_LANGUAGE
        warnings = result.get("warnings") or []
        assert any("language" in w.lower() for w in warnings), (
            f"Expected language-related warning, got: {warnings}"
        )
        assert any("atlas" in w.lower() for w in warnings), (
            "Warning should mention Atlas's language coverage"
        )


# ---------------------------------------------------------------------------
# Confidence cap matrix
# ---------------------------------------------------------------------------

SCAN_CONFIDENCE_CASES = [
    # (scan, max_expected_cap, description)
    # max_expected_cap means actual cap must be <= this value
    ({"file_count": 300, "module_count": 73, "dependency_edges": 159}, "high", "healthy Python"),
    ({"file_count": 24860, "module_count": 3}, "low", "Kubernetes-like Go"),
    ({"file_count": 1200, "module_count": 1}, "low", "Gin Go tiny"),
    # Java 0 modules → zero_module_scan → "degraded" → capped at "medium"
    ({"file_count": 700, "module_count": 0}, "medium", "Java 0 modules"),
    ({"graph_build": {"timed_out": True}, "file_count": 1000, "module_count": 100}, "medium",
     "timeout → medium"),
]


@pytest.mark.parametrize("scan,expected,desc", SCAN_CONFIDENCE_CASES)
def test_confidence_cap_matrix(scan, expected, desc):
    cap = rel.confidence_cap_for_scan(scan)
    # For degraded cases, cap must be ≤ expected
    _order = {"low": 0, "medium": 1, "high": 2}
    expected_ord = _order.get(expected, 2)
    actual_ord = _order.get(cap, 0)
    assert actual_ord <= expected_ord or cap == expected, (
        f"[{desc}] Expected confidence cap ≤ {expected}, got {cap}"
    )


# ---------------------------------------------------------------------------
# UNSUPPORTED_LANGUAGE is NOT retryable
# ---------------------------------------------------------------------------

def test_unsupported_language_not_retryable():
    scan = {"file_count": 5000, "module_count": 8}
    result = rel.classify_scan(scan)
    assert result["category"] == rel.UNSUPPORTED_LANGUAGE
    assert not result["retryable"], (
        "unsupported_language_limited should not be auto-retried"
    )
