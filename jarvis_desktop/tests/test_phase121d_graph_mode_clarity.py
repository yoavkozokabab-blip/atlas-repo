"""Phase 121D — graph mode clarity (metrics, badges, defaults)."""

from __future__ import annotations

from pathlib import Path

from jarvis_desktop import api


def _static(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "static" / name).read_text(encoding="utf-8")


def test_hierarchy_default_threshold_is_1000():
    assert api.GRAPH_DEFAULT_HIERARCHY_THRESHOLD == 1000
    assert api._graph_recommended_view(999) == "module"
    assert api._graph_recommended_view(1000) == "hierarchy"


def test_module_view_no_misleading_warning_for_small_massive_repo(monkeypatch):
    """Size-only massive (e.g. FINAL_ALGO) should not warn on module view when <1000 modules."""
    node_count = 216
    fake_graph = {
        "graph_scope": "production",
        "nodes": [
            {"id": f"module:m{i}", "type": "module", "path": f"p/m{i}.py", "dotted": f"p.m{i}"}
            for i in range(node_count)
        ],
        "edges": [],
        "statistics": {"import_cycles": []},
    }
    api._STATE.update(
        {
            "graph": fake_graph,
            "index": {"subsystems": []},
            "risks": {"ranked_modules": []},
            "scan": {"massive_mode": True, "massive_reason": {"size": True}},
        }
    )
    payload = api.current_graph("module")
    assert payload["view"] == "module"
    assert payload["node_count"] == node_count
    assert not payload.get("render_warning")


def test_frontend_mode_clarity_markers():
    app = _static("app.js")
    html = _static("index.html")
    css = _static("styles.css")
    assert "GRAPH_HIERARCHY_THRESHOLD = 1000" in app
    assert "renderGraphModeMetrics" in app
    assert "formatEntitySummary" in app
    assert "graphViewToastMessage" in app
    assert "showFullModuleGraph" in app
    assert "massiveModeBanner" in html
    assert "graphModeBadge" in html
    assert "graphEntitySummary" in html
    assert ".graph-mode-badge" in css
    assert "Architecture Overview" in app


def test_subsystem_payload_exposes_totals_for_underlying_row():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    assert api.scan_repository(str(root))["ok"]
    module = api.current_graph("module")
    overview = api.current_graph("subsystem")
    assert overview["total_modules"] == module["total_modules"]
    assert overview["node_count"] < module["node_count"]
