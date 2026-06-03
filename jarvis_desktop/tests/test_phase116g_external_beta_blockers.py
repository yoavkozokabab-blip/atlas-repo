"""Phase 116G desktop release-blocker regressions."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from jarvis_desktop import analytics, api, graph_build, system_browse

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _scan_stub(**overrides):
    scan = {
        "graph_scope": "production",
        "degraded": False,
        "module_count": 8144,
        "dependency_edges": 13224,
        "resolved_imports": 13224,
        "unresolved_imports": 69039,
        "external_package_imports": 232,
        "import_cycle_count": 0,
    }
    scan.update(overrides)
    return scan


def test_high_unresolved_ratio_marks_graph_partial_and_discloses_metrics():
    health = api._graph_health(_scan_stub())

    assert health["label"] == "partial"
    assert health["degraded"] is True
    assert health["resolved_imports"] == 13224
    assert health["unresolved_imports"] == 69039
    assert health["external_package_imports"] == 232
    assert health["unresolved_ratio"] > 0.8
    # Phase 123 — honest, non-alarmist notice (data trust): the metric counts
    # imports leaving the internal module set (external + stdlib + unresolved
    # internal), so the notice must disclose that rather than implying breakage.
    assert health["notice"]
    assert "outside the internal module set" in health["notice"]


def test_small_unresolved_count_does_not_overstate_partial_health():
    health = api._graph_health(
        _scan_stub(
            dependency_edges=20,
            resolved_imports=20,
            unresolved_imports=2,
            external_package_imports=1,
        )
    )

    assert health["label"] == "healthy"
    assert health["degraded"] is False
    assert health["notice"] == ""


def test_language_breakdown_reports_resolution_metrics():
    graph = {
        "nodes": [
            {"type": "module", "path": "src/a.ts", "language": "typescript"},
            {"type": "module", "path": "src/b.ts", "language": "typescript"},
        ],
        "edges": [
            {"type": "imports", "from": "module:src/a", "to": "module:src/b", "resolved": True},
        ],
        "statistics": {"unresolved_counts": {"imports_external": 3}},
        "external_package_count": 2,
        "external_package_import_count": 3,
    }

    breakdown = graph_build._language_breakdown(graph)

    assert breakdown["resolved_imports"] == 1
    assert breakdown["unresolved_imports"] == 3
    assert breakdown["external_packages"] == 2
    assert breakdown["external_package_imports"] == 3
    assert breakdown["unresolved_ratio"] == 0.75


def test_ui_shows_partial_graph_warning_and_resolution_metrics():
    app = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "Graph is partial: many imports could not be resolved." not in app
    assert "sum.graph_health?.notice" in app
    assert "Resolved imports" in app
    # Phase 134 — the cockpit now splits unresolved into internal vs external/stdlib
    # vs dynamic/optional (clearer than a single ambiguous "Unresolved imports").
    assert "Unresolved internal" in app
    assert "External / stdlib" in app
    assert "Dynamic / optional" in app


def test_native_picker_requests_foreground_window(monkeypatch):
    calls: list[str] = []

    class FakeRoot:
        def withdraw(self):
            calls.append("withdraw")

        def attributes(self, name, value):
            calls.append(f"attributes:{name}:{value}")

        def lift(self):
            calls.append("lift")

        def focus_force(self):
            calls.append("focus_force")

        def update_idletasks(self):
            calls.append("update_idletasks")

        def update(self):
            calls.append("update")

        def destroy(self):
            calls.append("destroy")

    root = FakeRoot()
    tkinter = types.ModuleType("tkinter")
    tkinter.Tk = lambda: root
    tkinter.filedialog = types.SimpleNamespace(
        askdirectory=lambda **kwargs: calls.append(f"dialog:{kwargs['title']}") or ""
    )
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)

    assert system_browse._pick_folder_native() == ""
    assert calls == [
        "withdraw",
        "attributes:-topmost:True",
        "lift",
        "focus_force",
        "update_idletasks",
        "update",
        "dialog:Choose a repository folder",
        "destroy",
    ]


def test_analytics_error_details_are_not_exposed(monkeypatch, tmp_path):
    analytics.reset_analytics_for_tests()
    monkeypatch.setenv("JARVIS_DESKTOP_DATA", str(tmp_path / "data"))

    def deny(*_args, **_kwargs):
        raise PermissionError("api_key=LEAK_ME")

    monkeypatch.setattr(analytics.os, "makedirs", deny)
    result = analytics.track_event("probe")
    snapshot = analytics.status_snapshot()

    assert result["ok"] is False
    assert result["error"] == "analytics_unavailable"
    assert "LEAK_ME" not in str(result)
    assert snapshot["telemetry_error"] == "PermissionError"
