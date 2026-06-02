"""Phase 116D — browse endpoint hotfix + subsystem graph visual sizing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from jarvis_desktop import api, server, system_browse

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _small_repo(tmp_path: Path) -> Path:
    root = tmp_path / "small"
    _write(root / "core" / "hub.py", "def hub():\n    return 1\n")
    for name in ("a", "b"):
        _write(root / f"{name}.py", f"from core.hub import hub\n\ndef run_{name}():\n    return hub()\n")
    return root


@pytest.fixture()
def small_scan(tmp_path):
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None})
    result = api.scan_repository(str(_small_repo(tmp_path)))
    assert result["ok"], result
    return result
UNIVERSE_JS = STATIC_DIR / "universe.js"
APP_JS = STATIC_DIR / "app.js"


def test_subsystem_visual_size_is_clamped():
    small = api._subsystem_visual_size(1, 0.0)
    huge = api._subsystem_visual_size(500_000, 100.0)
    assert 5.0 <= small["visual_size"] <= 14.0
    assert 5.0 <= huge["visual_size"] <= 14.0
    assert small["hub_scale"] <= 2.5
    assert huge["hub_scale"] <= 2.5


def test_subsystem_visual_size_uses_logarithmic_growth():
    low = api._subsystem_visual_size(10, 0.0)["visual_size"]
    mid = api._subsystem_visual_size(1_000, 0.0)["visual_size"]
    high = api._subsystem_visual_size(500_000, 0.0)["visual_size"]
    assert low < mid <= high <= 14.0
    assert high - mid < mid - low


def test_huge_subsystem_cannot_exceed_max_radius(small_scan):
    graph = api.current_graph("subsystem")
    assert graph["ok"]
    for node in graph["nodes"]:
        assert node["visual_size"] <= 14.0
        assert node["hub_scale"] <= 2.5
        assert node["size"] <= 14.0


def test_subsystem_graph_payload_includes_visual_size(small_scan):
    graph = api.current_graph("subsystem")
    assert graph.get("view") == "subsystem"
    assert graph["nodes"]
    for node in graph["nodes"]:
        assert "visual_size" in node
        assert "hub_scale" in node
        assert node["graph_view"] == "subsystem"


def test_browse_route_registered_in_audit():
    documented = {(m, p) for m, p in server.ROUTES}
    assert ("POST", "/api/system/browse-folder") in documented


def test_browse_mocked_success(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(system_browse, "_pick_folder_native", lambda: str(root))
    status, payload = server.dispatch("POST", "/api/system/browse-folder")
    assert status == 200
    assert payload["ok"] is True
    assert payload["path"] == str(root.resolve())


def test_browse_mocked_cancel(monkeypatch):
    monkeypatch.setattr(system_browse, "_pick_folder_native", lambda: "")
    status, payload = server.dispatch("POST", "/api/system/browse-folder")
    assert status == 200
    assert payload["ok"] is True
    assert payload["cancelled"] is True


def test_browse_mocked_unsupported(monkeypatch):
    def _fail() -> str:
        raise RuntimeError("headless")

    monkeypatch.setattr(system_browse, "_pick_folder_native", _fail)
    status, payload = server.dispatch("POST", "/api/system/browse-folder")
    assert status == 200
    assert payload["ok"] is False
    assert payload["code"] == "unsupported_browse_dialog"
    assert payload["message"] == "Paste the folder path manually."


def test_frontend_route_audit_includes_browse():
    calls: set[tuple[str, str]] = set()
    text = APP_JS.read_text(encoding="utf-8")
    for match in re.finditer(r"""\bapi\(\s*["`](/api/[^"`?]+)(?:\?[^"`]*)?["`](?:\s*,\s*["`](GET|POST)["`])?""", text):
        calls.add(((match.group(2) or "GET"), server.normalize_api_path(match.group(1))))
    assert ("POST", "/api/system/browse-folder") in calls
    missing = sorted(calls - set(server.ROUTES))
    assert not missing


def test_graph_mode_switch_clears_stale_graph_state():
    app = APP_JS.read_text(encoding="utf-8")
    start = app.index("function setGraphView(")
    end = app.index("function renderHierarchyBreadcrumb()", start)
    body = app[start:end]
    assert "STATE.graph = null" in body
    assert "STATE.graph3d = null" in body


def test_universe_subsystem_scaling_helpers_present():
    text = UNIVERSE_JS.read_text(encoding="utf-8")
    assert "function subsystemNodeScale(node)" in text
    assert "function fitGraphCamera(fg, nodes)" in text
    assert "d3.forceCollide" in text
    assert "function moduleNodeScale" in text
    assert "Math.min(18, node.visual_size" in text
