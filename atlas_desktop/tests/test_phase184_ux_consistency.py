"""Phase 184 — final UX consistency regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "atlas_desktop" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_canonical_workflow_names_in_index():
    html = _read("index.html")
    assert "Repository Analysis" in html
    assert "Implementation Plan" in html
    assert "Build implementation plan" in html
    assert "Failure Investigation" in html
    assert "Change Impact" in html
    assert ">Graph<" in html
    assert "Codebase Map" in html
    assert "Build Plan" not in html
    assert "Change Plan" not in html
    assert "Generate Change Plan" not in html


def test_scan_success_uses_ask_cta():
    html = _read("index.html")
    block = html.split('id="scanSuccess"', 1)[1].split("</section>", 1)[0]
    assert "Analyze repository" in block
    assert "Open Map" in block


def test_demo_page_cleaned():
    html = _read("demo.html")
    assert "demo.mp4" not in html
    assert "placeholder" not in html.lower()
    assert "coming soon" not in html.lower()
    assert "Open Atlas" in html


def test_support_copy_consistency():
    html = _read("support.html")
    assert "No Python required (installer)" in html
    assert "(installer)" in html and "(source" in html
    assert "press Send in <b>Ask Atlas</b> to see cited files" in html
    assert "Rescan saved repository" in html


def test_engineering_language_scrubbed_in_app():
    app = _read("app.js")
    assert "degraded/partial mode" not in app
    assert "target not in graph — heuristic" not in app
    assert "Building AI context packets" not in app
    assert "Estimate only — not in last scan" in app
    assert "atlasFriendlyGraphHealth" in app


def test_atlas_copy_helpers_shipped():
    js = _read("atlas_copy.js")
    assert "atlasFriendlyGraphHealth" in js
    assert "Phase" not in js.split("*/")[0]


def test_marketing_and_changelog_naming():
    assert "What Breaks" in _read("landing.html")
    assert "<b>Debug</b>" in _read("changelog.html")
    assert "<b>What breaks?</b>" in _read("changelog.html")
    assert "<b>Plan Change</b>" in _read("changelog.html")
    # about.html keeps its committed copy — the secondary-surface vocabulary
    # rewrite is deferred to its own change (see engineering-analyst checkpoint).
    assert "debug results are ranked hypotheses" in _read("about.html")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
