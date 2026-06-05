"""Phase 140 — regression tests for scan reliability (degraded detection, retry,
failure taxonomy). Reliability hardening only; no intelligence/UI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jarvis_desktop import reliability as rel  # noqa: E402


# --------------------------------------------------------------------------
# Classification taxonomy
# --------------------------------------------------------------------------
@pytest.mark.parametrize("scan,expected,degraded", [
    ({"ok": True, "file_count": 5000, "module_count": 0, "dependency_edges": 0},
     rel.ZERO_MODULE_SCAN, True),
    ({"ok": True, "file_count": 2000, "module_count": 1689, "dependency_edges": 0},
     rel.ZERO_EDGE_GRAPH, True),
    ({"ok": True, "file_count": 9000, "module_count": 100, "dependency_edges": 50,
      "graph_build": {"timed_out": True}}, rel.TIMEOUT, True),
    ({"ok": True, "file_count": 9000, "module_count": 100, "dependency_edges": 50,
      "degraded": True, "graph_detail": "full"}, rel.PARTIAL_GRAPH, True),
    ({"ok": True, "file_count": 3000, "module_count": 800, "dependency_edges": 900,
      "unresolved_imports": 4000, "unresolved_ratio": 0.95}, rel.UNRESOLVED_EXPLOSION, True),
    ({"ok": True, "file_count": 6868, "module_count": 929, "dependency_edges": 2916,
      "graph_detail": "imports"}, rel.OK, False),
    ({"ok": True, "file_count": 12, "module_count": 0, "dependency_edges": 0},
     rel.EMPTY_REPO, False),
    ({"ok": False, "error": "boom", "code": "scan_failed"}, rel.SCAN_FAILED, True),
])
def test_classify_scan(scan, expected, degraded):
    a = rel.classify_scan(scan)
    assert a["category"] == expected
    assert a["degraded"] is degraded
    assert a["healthy"] is (not degraded)


def test_partial_imports_graph_is_not_degraded():
    # An over-cap but complete import-level graph is healthy, not partial.
    a = rel.classify_scan({"ok": True, "file_count": 25893, "module_count": 9709,
                           "dependency_edges": 36013, "degraded": True,
                           "graph_detail": "imports"})
    assert a["category"] == rel.OK and a["healthy"] is True


# --------------------------------------------------------------------------
# Retry policy — only safe transient categories
# --------------------------------------------------------------------------
def test_only_zero_module_is_retryable():
    zero = rel.classify_scan({"ok": True, "file_count": 5000, "module_count": 0,
                              "dependency_edges": 0})
    assert rel.is_retryable(zero) is True
    for scan in [
        {"ok": True, "file_count": 9000, "module_count": 100, "dependency_edges": 50,
         "graph_build": {"timed_out": True}},                 # timeout — not safe to auto-retry
        {"ok": True, "file_count": 2000, "module_count": 1689, "dependency_edges": 0},  # zero-edge
        {"ok": False, "error": "boom", "code": "scan_failed"},
    ]:
        assert rel.is_retryable(rel.classify_scan(scan)) is False


def test_memory_pressure_flagged():
    a = rel.classify_scan({"ok": True, "file_count": 6868, "module_count": 929,
                           "dependency_edges": 2916, "graph_detail": "imports"},
                          peak_rss_mb=4096)
    assert any("memory" in w.lower() for w in a["warnings"])


# --------------------------------------------------------------------------
# Warnings surface immediately for degraded scans
# --------------------------------------------------------------------------
def test_degraded_scans_emit_warnings():
    for scan in [
        {"ok": True, "file_count": 5000, "module_count": 0, "dependency_edges": 0},
        {"ok": True, "file_count": 2000, "module_count": 1689, "dependency_edges": 0},
        {"ok": True, "file_count": 9000, "module_count": 100, "dependency_edges": 50,
         "graph_build": {"timed_out": True}},
    ]:
        assert rel.scan_warnings(scan), scan
    # healthy scan = no warnings
    assert rel.scan_warnings({"ok": True, "file_count": 6868, "module_count": 929,
                              "dependency_edges": 2916, "graph_detail": "imports"}) == []


def test_every_category_is_in_taxonomy():
    cats = {rel.OK, rel.SCAN_CRASH, rel.SCAN_FAILED, rel.ZERO_MODULE_SCAN,
            rel.ZERO_EDGE_GRAPH, rel.PARTIAL_GRAPH, rel.TIMEOUT,
            rel.UNRESOLVED_EXPLOSION, rel.MEMORY_PRESSURE, rel.EMPTY_REPO,
            rel.UNSUPPORTED_LANGUAGE}
    # fault set is a coherent subset
    assert rel.FAULT_CATEGORIES <= cats
    assert rel.OK not in rel.FAULT_CATEGORIES
    assert rel.EMPTY_REPO not in rel.FAULT_CATEGORIES
    assert rel.RETRYABLE_CATEGORIES <= rel.FAULT_CATEGORIES


# --------------------------------------------------------------------------
# Live wiring: scan_repository attaches a reliability assessment
# --------------------------------------------------------------------------
def test_scan_repository_attaches_reliability(tmp_path):
    from jarvis_desktop import api
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "core.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (root / "pkg" / "app.py").write_text("from pkg.core import helper\n\n\ndef run():\n    return helper()\n", encoding="utf-8")
    scan = api.scan_repository(str(root))
    assert scan["ok"]
    assert "reliability" in scan and "category" in scan["reliability"]
    assert "health_warnings" in scan
    assert scan["reliability"]["category"] in {rel.OK, rel.ZERO_EDGE_GRAPH, rel.EMPTY_REPO}
