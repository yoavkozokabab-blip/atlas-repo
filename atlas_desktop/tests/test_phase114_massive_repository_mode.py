"""Phase 114 — massive repository runtime/product support."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_desktop import api, server


def _write(path: Path, text: str = "x = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(root / "backend" / "main.py", "from backend.util import v\n\ndef run():\n    return v()\n")
    _write(root / "backend" / "util.py", "def v():\n    return 1\n")
    _write(root / "frontend" / "app.ts", "export const x = 1;\n")
    _write(root / "README.md", "# repo\n")
    _write(root / "node_modules" / "skip.js", "ignored\n")
    _write(root / "dist" / "bundle.js", "ignored\n")
    return root


@pytest.fixture(autouse=True)
def reset_state():
    api._STATE.update(
        {
            "path": None,
            "scan": None,
            "graph": None,
            "index": None,
            "risks": None,
            "demo_mode": False,
            "last_scope": {"mode": "entire_repo"},
            "scan_cache": {},
            "scan_job": {"id": None, "cancelled": False, "stage": "idle"},
        }
    )
    yield


def test_pre_scan_estimator(tmp_path):
    root = _repo(tmp_path)
    est = api.pre_scan_estimate(str(root), {"mode": "entire_repo"})
    assert est["ok"]
    assert est["total_files"] >= est["code_files"] >= 2
    assert est["repo_size_bytes"] > 0
    assert ".git" in est["ignored_folders"]
    assert ".py" in est["languages"] or ".ts" in est["languages"]


def test_ignore_rules_and_scope_selector(tmp_path):
    root = _repo(tmp_path)
    py = api.pre_scan_estimate(str(root), {"mode": "python_only"})
    assert py["ok"] and ".ts" not in py["languages"]
    be = api.pre_scan_estimate(str(root), {"mode": "backend"})
    assert be["ok"] and be["code_files"] >= 2
    fe = api.pre_scan_estimate(str(root), {"mode": "frontend"})
    assert fe["ok"] and fe["code_files"] >= 1


def test_massive_mode_trigger_manual(tmp_path):
    root = _repo(tmp_path)
    scan = api.scan_repository(str(root), {"mode": "entire_repo", "manual_massive_mode": True})
    assert scan["ok"]
    assert scan["massive_mode"] is True
    assert scan["massive_reason"]["manual"] is True


def test_cache_hit_and_miss(tmp_path):
    root = _repo(tmp_path)
    first = api.scan_repository(str(root), {"mode": "entire_repo"})
    assert first["ok"] and first["cache"]["hit"] is False
    second = api.scan_repository(str(root), {"mode": "entire_repo"})
    assert second["ok"] and second["cache"]["hit"] is True


def test_cancel_scan_flag():
    assert api.cancel_scan()["ok"]
    status = api.scan_status()
    assert status["ok"]
    assert status["job"]["cancelled"] is True


def test_large_graph_keeps_module_view_recommends_hierarchy(monkeypatch):
    node_count = 5105
    fake_graph = {
        "graph_scope": "production",
        "degraded": False,
        "nodes": [{"id": f"module:m{i}", "type": "module", "path": f"pkg/m{i}.py", "dotted": f"pkg.m{i}"} for i in range(node_count)],
        "edges": [],
        "statistics": {"import_cycles": [], "top_imported_modules": [], "unresolved_counts": {}},
    }
    api._STATE.update(
        {
            "graph": fake_graph,
            "index": {"subsystems": [{"name": "pkg", "entry_files": [], "role_counts": {"production_code": node_count}}]},
            "risks": {"ranked_modules": []},
            "scan": {"massive_mode": True, "graph_scope": "production"},
        }
    )
    payload = api.current_graph("module")
    assert payload["ok"]
    assert payload["view"] == "module"
    assert payload["defaulted_to_subsystem"] is False
    assert payload["recommended_view"] == "hierarchy"
    assert payload["render_warning"]
    overview = api.current_graph("subsystem")
    assert overview["view"] == "subsystem"
    assert overview.get("architecture_clusters") is True


def test_hierarchy_graph_levels(tmp_path):
    root = _repo(tmp_path)
    assert api.scan_repository(str(root), {"mode": "entire_repo"})["ok"]
    sub = api.current_hierarchy_graph("subsystem")
    assert sub["ok"] and sub["level"] == "subsystem"
    assert sub["counts"]["modules"] >= 1
    pkg = api.current_hierarchy_graph("package")
    assert pkg["ok"] and pkg["level"] == "package"
    assert "risk_hotspots" in pkg["counts"]
    mod = api.current_hierarchy_graph("module", "backend")
    assert mod["ok"] and mod["level"] == "module"
    assert mod["counts"]["files"] == mod["counts"]["modules"]


def test_server_routes_for_massive_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_account_gate_failure", lambda: None)
    root = _repo(tmp_path)
    assert server.dispatch("POST", "/api/repositories/estimate", {"path": str(root)})[1]["ok"]
    assert server.dispatch("POST", "/api/repositories/scan", {"path": str(root), "scope": {"mode": "backend"}})[1]["ok"]
    assert server.dispatch("GET", "/api/repositories/current/scan-status")[1]["ok"]
    assert server.dispatch("POST", "/api/repositories/current/cancel-scan")[1]["ok"]
    assert server.dispatch("GET", "/api/repositories/current/hierarchy-graph")[1]["ok"]


def test_frontend_hierarchy_navigation_state_markers():
    static = Path(__file__).resolve().parents[1] / "static"
    app = (static / "app.js").read_text(encoding="utf-8")
    html = (static / "index.html").read_text(encoding="utf-8")
    for needle in (
        "navigateHierarchy(",
        "renderHierarchyBreadcrumb(",
        "handleHierarchyClick(",
        "backToOverview(",
        "hierarchyBreadcrumb",
        "hierarchyCounts",
    ):
        assert needle in app or needle in html, needle
