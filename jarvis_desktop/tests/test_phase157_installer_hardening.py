"""Phase 157 — installer reliability and self-test hardening.

Covers the installer self-test, shortcut/registry/browser failure handling,
SmartScreen guidance, and obvious support-bundle location. No intelligence,
semantic resolver, benchmarks, marketing site, or billing code is touched.
"""

from __future__ import annotations

from pathlib import Path

from jarvis_desktop import api, server
from jarvis_desktop import install_support

ROOT = Path(__file__).resolve().parents[2]
RUN_ATLAS = ROOT / "run_atlas.py"
ISS = ROOT / "packaging" / "installer" / "Atlas.iss"
INSTALL_NOTES = ROOT / "packaging" / "installer" / "install_notes.txt"
INSTALLER_BUILD = ROOT / "packaging" / "installer" / "installer_build.ps1"
SERVER = ROOT / "jarvis_desktop" / "server.py"
SUPPORT = ROOT / "jarvis_desktop" / "static" / "support.html"
SUPPORT_JS = ROOT / "jarvis_desktop" / "static" / "support.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Installer self-test
# --------------------------------------------------------------------------- #
def test_installer_self_test_structure():
    result = install_support.installer_self_test()
    assert result["ok"] is True
    assert "ready" in result
    ids = {c["id"] for c in result["checks"]}
    assert {"executable", "directories", "shortcuts", "browser"} <= ids
    for check in result["checks"]:
        assert "label" in check and "ok" in check and "detail" in check


def test_installer_self_test_verifies_executable_shortcuts_browser():
    result = install_support.installer_self_test()
    by_id = {c["id"]: c for c in result["checks"]}
    # Atlas.exe / launcher
    assert "Atlas" in by_id["executable"]["label"] or "launcher" in by_id["executable"]["label"]
    # shortcuts + browser are present (optional in source mode, never fatal)
    assert by_id["shortcuts"].get("optional") in (True, False)
    assert by_id["browser"].get("optional") is True
    # In source mode the self-test should still be "ready" (no critical failures).
    assert result["ready"] is True
    assert result["critical_failures"] == []


def test_self_test_route_registered_and_dispatches():
    assert server.route_is_registered("GET", "/api/system/self-test")
    status, payload = server.dispatch("GET", "/api/system/self-test")
    assert status == 200
    assert payload["ok"] is True
    assert "checks" in payload


def test_api_exposes_installer_self_test():
    result = api.installer_self_test()
    assert result["ok"] is True


def test_launcher_has_self_test_cli():
    text = _read(RUN_ATLAS)
    assert "--self-test" in text
    assert "_run_self_test_cli" in text
    assert "installer_self_test" in text


# --------------------------------------------------------------------------- #
# Installer reliability: shortcuts, notes, build self-test
# --------------------------------------------------------------------------- #
def test_inno_creates_shortcuts_and_shows_notes():
    text = _read(ISS)
    assert "{group}" in text          # Start menu shortcut
    assert "autodesktop" in text      # Desktop shortcut
    assert "InfoBeforeFile" in text   # beta install notes shown before install


def test_installer_build_runs_self_test():
    text = _read(INSTALLER_BUILD)
    assert "Test-StagedInstaller" in text
    assert "self-test" in text.lower()
    assert "Atlas.exe" in text


def test_browser_auto_open_failure_is_handled():
    text = _read(SERVER)
    assert "browser did not auto-open" in text
    assert "_log_launcher" in text


# --------------------------------------------------------------------------- #
# SmartScreen guidance
# --------------------------------------------------------------------------- #
def test_smartscreen_guidance_in_install_notes():
    text = _read(INSTALL_NOTES).lower()
    assert "smartscreen" in text
    assert "run anyway" in text
    assert "no python" in text


# --------------------------------------------------------------------------- #
# Support: self-test surface + obvious bundle location
# --------------------------------------------------------------------------- #
def test_support_page_has_self_test_and_bundle_location():
    html = _read(SUPPORT)
    assert "Installer self-test" in html
    assert "Downloads" in html
    js = _read(SUPPORT_JS)
    assert "supportRunSelfTest" in js
    assert "Downloads" in js
