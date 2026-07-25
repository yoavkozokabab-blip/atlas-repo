"""Phase 143 — one-click installer and support bundle."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest

from atlas_desktop import api, install_support, server

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _demo_loaded(tmp_path, local_guest_account):
    _, loaded = server.dispatch("POST", "/api/demo/load", {"pack": "small"})
    if not loaded.get("ok"):
        repo = tmp_path / "support-fixture"
        repo.mkdir()
        (repo / "app.py").write_text("print('atlas support fixture')\n", encoding="utf-8")
        _, loaded = server.dispatch("POST", "/api/repositories/scan", {"path": str(repo)})
        assert loaded.get("ok"), loaded
    yield


def test_startup_checks_pass_in_dev():
    checks = install_support.startup_checks()
    assert checks["ok"] is True
    assert checks["ready"] is True
    ids = {c["id"] for c in checks["checks"]}
    assert "python" in ids and "directories" in ids


def test_startup_status_route():
    _, env = server.dispatch("GET", "/api/system/startup-status")
    assert env["ok"] is True
    assert env["version"] == api.PRODUCT_VERSION
    assert env["startup"]["ready"] is True


def test_clear_cache_and_rebuild():
    _, clear = server.dispatch("POST", "/api/system/clear-cache")
    assert clear["ok"] is True
    _, rebuild = server.dispatch("POST", "/api/system/rebuild-index", {"rescan": True})
    assert rebuild["ok"] is True
    assert rebuild.get("rescanned") is True


def test_support_bundle_no_source_code():
    _, bundle = server.dispatch("POST", "/api/system/support-bundle")
    assert bundle["ok"] is True
    assert "atlas_support_bundle" in bundle["filename"]
    raw = base64.b64decode(bundle["content_base64"])
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        assert "diagnostics.json" in names
        assert "version.txt" in names
        assert "scan_metadata.json" in names
        for n in names:
            assert not n.endswith(".py")
            assert "/src/" not in n


def test_launcher_files_exist():
    assert (ROOT / "Launch Atlas.bat").is_file()
    assert (ROOT / "run_atlas.py").is_file()
    assert (ROOT / "Launch Atlas.vbs").is_file()
    static = Path(__file__).resolve().parents[1] / "static"
    assert (static / "support.html").is_file()
    assert (static / "support.js").is_file()


def test_phase143_report_exists():
    report = ROOT / "reports" / "phase143_installer_and_support.md"
    if not report.is_file():
        pytest.skip("historical phase report not shipped in the product repo")
