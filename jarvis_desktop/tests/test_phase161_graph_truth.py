"""Phase 161 — graph health truth, propagated into all outputs.

Kubernetes-style scans (24k files, 3 modules) must never report 'healthy'. The
unified vocabulary {healthy, partial, degraded, unsupported} is propagated from
the reliability assessment into the summary graph-health block.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from jarvis_desktop import api
from jarvis_desktop import reliability as rel


def _scan(**kw):
    base = {"graph_scope": "entire_repo", "module_count": 0, "dependency_edges": 0,
            "file_count": 0, "resolved_imports": 0, "unresolved_imports": 0}
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# Summary graph-health (api._graph_health) propagation
# --------------------------------------------------------------------------- #
def test_kubernetes_summary_not_healthy():
    gh = api._graph_health(_scan(file_count=24860, module_count=3, dependency_edges=0))
    assert gh["label"] != "healthy"
    assert gh["label"] == "unsupported"
    assert gh.get("reliability_category") == rel.UNSUPPORTED_LANGUAGE


def test_healthy_python_summary_is_healthy():
    gh = api._graph_health(_scan(file_count=300, module_count=73, dependency_edges=159,
                                 resolved_imports=159))
    assert gh["label"] == "healthy"


def test_zero_edge_many_modules_is_degraded():
    gh = api._graph_health(_scan(file_count=100, module_count=50, dependency_edges=0))
    assert gh["label"] == "degraded"


def test_summary_label_in_unified_vocabulary():
    for scan in (
        _scan(file_count=300, module_count=73, dependency_edges=159, resolved_imports=159),
        _scan(file_count=24860, module_count=3),
        _scan(file_count=100, module_count=50, dependency_edges=0),
        _scan(file_count=1200, module_count=1),
    ):
        gh = api._graph_health(scan)
        assert gh["label"] in ("healthy", "partial", "watch", "degraded", "unsupported", "empty")


def test_summary_carries_reliability_category():
    gh = api._graph_health(_scan(file_count=300, module_count=73, dependency_edges=159))
    assert "reliability_category" in gh


# --------------------------------------------------------------------------- #
# Reliability layer (unchanged truth — guards regressions)
# --------------------------------------------------------------------------- #
def test_reliability_kubernetes_unsupported():
    assert rel.graph_health_label({"file_count": 24860, "module_count": 3}) == "unsupported_language_limited"


def test_reliability_cap_kubernetes_low():
    assert rel.confidence_cap_for_scan({"file_count": 24860, "module_count": 3}) == "low"


def test_boundary_not_unsupported():
    # exactly at threshold should not be unsupported
    cat = rel.classify_scan({"file_count": 1000, "module_count": 25, "dependency_edges": 5})["category"]
    assert cat != rel.UNSUPPORTED_LANGUAGE
    # just over → unsupported
    cat2 = rel.classify_scan({"file_count": 1001, "module_count": 24})["category"]
    assert cat2 == rel.UNSUPPORTED_LANGUAGE
