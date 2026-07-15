"""Phase 152 — Windows installer / PyInstaller packaging smoke checks."""

from __future__ import annotations

import json

import pytest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "packaging"
DIST = ROOT / "dist" / "Atlas"
SPEC = PKG / "pyinstaller" / "atlas.spec"
ISS = PKG / "installer" / "Atlas.iss"


def test_packaging_files_exist():
    assert (PKG / "pyinstaller" / "atlas_entry.py").is_file()
    assert (PKG / "pyinstaller" / "build_atlas_exe.ps1").is_file()
    assert SPEC.is_file()
    assert ISS.is_file()
    assert (PKG / "installer" / "installer_build.ps1").is_file()


def test_spec_includes_required_assets():
    text = SPEC.read_text(encoding="utf-8")
    assert "atlas_desktop/static" in text
    assert "atlas_desktop/demo" in text
    assert "ATLAS_QUICKSTART" in text
    assert "external_repos" in text
    assert 'name="Atlas"' in text
    assert "console=False" in text
    assert '"assets"' in text
    assert "atlas.ico" in text


def test_inno_references_atlas_exe():
    text = ISS.read_text(encoding="utf-8")
    assert "Atlas.exe" in text
    assert "staging" in text
    assert "Atlas_Setup" in text
    assert "desktopicon" in text


def test_root_build_wrappers_delegate():
    root_build = (ROOT / "build_atlas_exe.ps1").read_text(encoding="utf-8")
    root_installer = (ROOT / "installer_build.ps1").read_text(encoding="utf-8")
    assert "packaging\\pyinstaller\\build_atlas_exe.ps1" in root_build
    assert "packaging\\installer\\installer_build.ps1" in root_installer


def test_frozen_entry_avoids_traceback_dialog():
    entry = (PKG / "pyinstaller" / "atlas_entry.py").read_text(encoding="utf-8")
    assert "disable_windowed_traceback" not in entry
    assert "excepthook" in entry
    # RC-1 opens the guided startup-error page instead of raw support.html.
    assert "startup-error.html" in entry


def test_dist_layout_when_built():
    if not (DIST / "Atlas.exe").is_file():
        return
    assert (DIST / "Atlas.exe").is_file()
    static = DIST / "atlas_desktop" / "static" / "support.html"
    if not static.is_file():
        static = next(DIST.rglob("support.html"), None)
    assert static and static.is_file(), "support.html missing from dist"
    demo = DIST / "atlas_desktop" / "demo" / "small_repo"
    if not demo.is_dir():
        demo = next(DIST.rglob("small_repo"), None)
    assert demo and demo.is_dir(), "sample demo repo missing from dist"
    assert (DIST / "assets" / "atlas.ico").is_file(), "packaged icon missing from dist"
    joined = "\n".join(str(p) for p in DIST.rglob("*")).lower()
    assert "external_repos" not in joined
    assert "\\.git\\" not in joined.replace("/", "\\")
    assert not any(p.name == ".git" for p in DIST.rglob(".git"))


def test_build_info_when_present():
    info_path = PKG / "installer" / "build_info.json"
    if not info_path.is_file():
        return
    data = json.loads(info_path.read_text(encoding="utf-8-sig"))
    assert data.get("version")
    assert data.get("build_date")
    commit = data.get("commit")
    if commit:
        assert re.fullmatch(r"[0-9a-f]{40}", commit)


def test_packaging_embeds_full_commit_hash():
    pyinstaller = (PKG / "pyinstaller" / "build_atlas_exe.ps1").read_text(encoding="utf-8")
    installer = (PKG / "installer" / "installer_build.ps1").read_text(encoding="utf-8")
    product_info = (ROOT / "atlas_desktop" / "product_info.py").read_text(encoding="utf-8")
    assert "rev-parse HEAD" in pyinstaller
    assert "rev-parse HEAD" in installer
    assert '"rev-parse", "HEAD"' in product_info
    assert "rev-parse --short HEAD" not in pyinstaller
    assert "rev-parse --short HEAD" not in installer
    assert '"--short", "HEAD"' not in product_info


def test_desktop_serves_favicon_from_packaged_icon():
    server = (ROOT / "atlas_desktop" / "server.py").read_text(encoding="utf-8")
    assert 'rel == "favicon.ico"' in server
    assert "image/x-icon" in server
    assert "assets\", \"atlas.ico" in server
    assert (PKG / "installer" / "assets" / "atlas.ico").is_file()


def test_phase152_report_exists():
    report = ROOT / "reports" / "phase152_windows_installer.md"
    if not report.is_file():
        pytest.skip("historical phase report not shipped in the product repo")
    body = report.read_text(encoding="utf-8").lower()
    assert "pyinstaller" in body
    assert "inno" in body
