"""Phase 116 — desktop multilang graph integration."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_desktop import api, graph_build


def test_merge_graphs_combines_python_and_js():
    py = {
        "repository_root": "/r",
        "nodes": [
            {"id": "repository:/r", "type": "repository", "root": "/r"},
            {"id": "module:a.py", "type": "module", "path": "a.py", "line_count": 1},
        ],
        "edges": [
            {"type": "contains", "from": "repository:/r", "to": "module:a.py", "resolved": True, "line": 1},
        ],
        "unresolved": {"imports_external": [], "calls_unresolved": [], "references_unresolved": []},
        "scope_diagnostics": {"files_kept": 1},
    }
    js = {
        "repository_root": "/r",
        "nodes": [
            {"id": "module:src/b", "type": "module", "path": "src/b.ts", "language": "typescript", "line_count": 2},
        ],
        "edges": [
            {
                "type": "imports",
                "from": "module:src/a",
                "to": "module:src/b",
                "resolved": True,
                "line": 1,
            },
        ],
        "unresolved": {"imports_external": [], "calls_unresolved": [], "references_unresolved": []},
        "scope_diagnostics": {"files_kept": 1},
        "external_package_count": 3,
    }
    merged = graph_build.merge_graphs(py, js)
    mods = [n for n in merged["nodes"] if n.get("type") == "module"]
    assert len(mods) == 2
    lb = merged.get("language_breakdown") or {}
    assert lb.get("typescript_modules") == 1
    assert lb.get("python_modules") == 1


def test_ts_sample_repo_scan_non_empty():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    result = api.scan_repository(str(root))
    assert result["ok"] is True
    assert result["module_count"] > 0
    assert result["dependency_edges"] > 0
    assert (result.get("language_breakdown") or {}).get("typescript_modules", 0) > 0


def test_multilang_risk_signals_marked_unavailable():
    root = Path(__file__).resolve().parents[1] / "demo" / "ts_sample_repo"
    api.scan_repository(str(root))
    risks = api.current_risks()
    ranked = risks.get("ranked_modules", [])
    ts_row = next((r for r in ranked if str(r.get("path", "")).endswith(".ts")), None)
    if ts_row:
        avail = ts_row.get("signal_availability") or {}
        assert avail.get("test_evidence") == "unavailable"


def test_frontend_language_breakdown_marker():
    text = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
    assert "typescript modules" in text
    assert "language_breakdown" in text
