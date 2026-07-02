"""Phase 112 — installer, demo pack, product tour, analytics, export bundle."""

from __future__ import annotations

import base64
import io
import os
import zipfile
from pathlib import Path

import pytest

from jarvis_desktop import analytics, api
from jarvis_desktop import server


@pytest.fixture(autouse=True)
def reset_state(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DESKTOP_DATA", str(tmp_path / "analytics"))
    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "demo_mode": False})
    analytics.reset_analytics_for_tests()
    yield


def test_demo_packs_list():
    packs = api.list_demo_packs()
    assert packs["ok"]
    ids = {p["id"] for p in packs["packs"]}
    # RC-1 exposes all three sizes; "small" is the instant first-run default.
    assert ids == {"small", "medium", "large"}
    assert packs["default"] == "small"
    for pack_id in ids:
        assert api.demo_repo_path(pack_id)
        assert Path(api.demo_repo_path(pack_id)).is_dir()
    # Hidden pack stays loadable directly (tours / tests / deep links).
    assert api.load_demo_mode("small")["ok"]


def test_load_demo_pack_sizes():
    small = api.load_demo_mode("small")
    assert small["ok"] and small["demo_pack"] == "small"
    assert small["module_count"] >= 3

    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "demo_mode": False})
    medium = api.load_demo_mode("medium")
    assert medium["ok"] and medium["module_count"] >= small["module_count"]

    api._STATE.update({"path": None, "scan": None, "graph": None, "index": None, "risks": None, "demo_mode": False})
    large = api.load_demo_mode("large")
    assert large["ok"] and large["module_count"] >= medium["module_count"]


def test_export_demo_bundle():
    assert api.load_demo_mode("small")["ok"]
    bundle = api.export_demo_bundle()
    assert bundle["ok"]
    assert bundle["filename"].endswith(".zip")
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "summary.json" in names
        assert "architecture_report.txt" in names
        assert "graph_topology.svg" in names
        assert "context_claude_compact.txt" in names
        assert "landing_assets/checklists.md" in names


def test_local_analytics_writes():
    api.track_analytics_event("scan_completed", modules=5)
    api.track_analytics_event("graph_opened")
    api.track_analytics_event("copilot_question", mode="risk")
    summary = api.analytics_overview()
    assert summary["ok"] and summary["local_only"]
    assert summary["scans_completed"] >= 1
    assert summary["graph_opens"] >= 1
    assert summary["copilot_questions"] >= 1
    assert Path(summary["path"]).is_file()


def test_analytics_routes():
    status, payload = server.dispatch("POST", "/api/analytics/event", {"event": "export_created", "target": "claude"})
    assert status == 200 and payload["ok"]
    status, summary = server.dispatch("GET", "/api/analytics/summary")
    assert status == 200 and summary["exports"] >= 1


def test_demo_routes(beta_account):
    status, packs = server.dispatch("GET", "/api/demo/packs")
    assert status == 200 and packs["ok"]
    status, demo = server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    assert status == 200 and demo["ok"] and demo["demo_mode"]
    status, bundle = server.dispatch("POST", "/api/demo/export-bundle")
    assert status == 200 and bundle["ok"] and bundle["content_base64"]


def test_demo_load_blocked_without_account(monkeypatch):
    # Production protection intact: with no signed-in account, the gate blocks.
    monkeypatch.setattr(
        server.accounts_client,
        "get_account_state",
        lambda: {"authenticated": False, "user": None, "license": {"valid": False}},
    )
    status, demo = server.dispatch("POST", "/api/demo/load", {"pack": "medium"})
    assert status == 403
    assert demo["code"] in ("account_required", "license_required")


def test_tour_still_works_after_demo_load():
    assert api.load_demo_mode("medium")["ok"]
    tour = api.current_tour("module")
    assert tour["ok"] and tour["stop_count"] == 5


def test_installer_files_exist():
    # Canonical installer lives under packaging/installer (the legacy
    # top-level installer/jarvis.iss was retired).
    root = Path(__file__).resolve().parents[2]
    assert (root / "packaging" / "installer" / "Atlas.iss").is_file()
    assert (root / "packaging" / "installer" / "installer_build.ps1").is_file()
    assert (root / "installer_build.ps1").is_file()
    assert (root / "Launch Atlas.bat").is_file()
    assert (root / "run_atlas.py").is_file()


def test_frontend_phase112_markers():
    static = root = Path(__file__).resolve().parents[1] / "static"
    app = (static / "app.js").read_text(encoding="utf-8")
    html = (static / "index.html").read_text(encoding="utf-8")
    for needle in (
        "startProductTour",
        "exportDemoBundle",
        "renderDemoPackPicker",
        "demoPackList",
        "productTourPanel",
        "presentationBadge",
    ):
        assert needle in app or needle in html, needle


def test_builder_core_unchanged_import_surface():
    """Phase 112 must not add new Builder Core analysis entry points in api imports."""
    text = Path(__file__).resolve().parents[1].joinpath("api.py").read_text(encoding="utf-8")
    assert "from builder_core import architectural_risk, repository_understanding" in text
    assert "from builder_core.bug_intelligence import depgraph" in text
    assert "compact_packets" not in text
