"""Phase 184 — final UX consistency regression tests.

Verifies:
  - No legacy workflow names (Build Plan, Investigation, Impact Analysis)
  - No placeholder / demo.mp4 content
  - No raw engineering language visible to users
  - Correct canonical names throughout: Change Plan, Debug, What Breaks
  - Empty-state / "(none)" items are suppressed
  - First-user path copy is consistent
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "jarvis_desktop" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


# ── Task 1: Naming unification ──────────────────────────────────────────────

def test_no_legacy_workflow_names_in_html():
    """User-facing HTML must not use any of the removed workflow names."""
    # These files are user-facing content
    for fname in ("index.html", "about.html", "changelog.html", "gallery.html",
                  "landing.html", "demo.html", "support.html", "quickstart.html"):
        html = _read(fname)
        assert "Build Plan" not in html, f"{fname}: 'Build Plan' found"
        assert "Impact Analysis" not in html, f"{fname}: 'Impact Analysis' found"
        # "Investigation" as a workflow name (capitalised, quoted, or as a heading)
        # but allow it as a common English noun in lowercase prose
        # Simple check: no capitalised standalone "Investigation" as a section name
        assert "<b>Investigation</b>" not in html, f"{fname}: '<b>Investigation</b>' found"
        assert ">Investigation<" not in html, f"{fname}: '>Investigation<' found"


def test_canonical_names_present_in_index():
    """index.html must use the three canonical workflow names."""
    html = _read("index.html")
    assert "Change Plan" in html
    assert "Debug" in html
    assert "What breaks?" in html or "What Breaks" in html


def test_button_says_generate_not_create():
    """The Change Plan action button must say 'Generate', not 'Create'."""
    html = _read("index.html")
    assert "Generate Change Plan" in html
    assert "Create Change Plan" not in html


def test_scan_success_says_generate():
    """Post-scan CTA says 'Generate your first Change Plan', not 'Create'."""
    html = _read("index.html")
    assert "Generate your first Change Plan" in html
    assert "Create your first Change Plan" not in html


def test_about_uses_debug_not_investigation():
    html = _read("about.html")
    assert "debug results are ranked hypotheses" in html
    assert "investigations are ranked hypotheses" not in html


def test_changelog_uses_canonical_names():
    cl = _read("changelog.html")
    assert "<b>Change Plan</b>" in cl
    assert "<b>Debug</b>" in cl
    assert "<b>What breaks?</b>" in cl
    # Legacy names must be gone
    assert "<b>Build Plan</b>" not in cl
    assert "<b>Investigation</b>" not in cl
    assert "<b>Impact analysis</b>" not in cl


def test_gallery_uses_what_breaks():
    html = _read("gallery.html")
    assert "What Breaks" in html
    assert "Impact Analysis" not in html


def test_landing_uses_what_breaks():
    html = _read("landing.html")
    assert "What Breaks" in html
    assert "Impact Analysis" not in html


# ── Task 2: Demo cleanup ─────────────────────────────────────────────────────

def test_demo_page_has_no_video_placeholder():
    html = _read("demo.html")
    assert "demo.mp4" not in html
    assert "Demo recording" not in html
    assert "coming soon" not in html.lower()
    assert "placeholder" not in html.lower()
    assert "Open Atlas" in html


def test_atlas_beta_js_markdown_headers_are_canonical():
    """Exported markdown bundle uses canonical section names."""
    js = _read("atlas_beta.js")
    assert '"## Change Plan"' in js
    assert '"## Debug"' in js
    assert '"## What' in js        # "## What Breaks" or "## What breaks?"
    assert '"## Build Plan"' not in js
    assert '"## Investigation"' not in js
    assert '"## Impact"' not in js


# ── Task 5: Engineering language ─────────────────────────────────────────────

def test_no_engineering_jargon_in_user_strings_html():
    for fname in ("index.html", "support.html", "quickstart.html", "startup-error.html"):
        html = _read(fname)
        assert "telemetry unavailable" not in html.lower(), \
            f"{fname}: 'telemetry unavailable' found"
        assert "confidence cap" not in html.lower(), \
            f"{fname}: 'confidence cap' found"
        assert "fan-in" not in html.lower(), \
            f"{fname}: 'fan-in' found"
        assert "fan-out" not in html.lower(), \
            f"{fname}: 'fan-out' found"


def test_app_js_removes_engineering_terms():
    app = _read("app.js")
    assert "degraded/partial mode" not in app
    assert "fan-in / fan-out" not in app
    # plain-English replacement present
    assert "dependents / dependencies" in app
    assert "Some file links could not be resolved" in app


def test_app_js_impact_error_is_plain_english():
    app = _read("app.js")
    assert "Could not analyze what breaks" in app
    assert "Impact could not be analyzed" not in app


def test_studio_js_no_fan_in():
    js = _read("studio.js")
    # "Fan-in" should not appear as user-visible copy (may exist in comments)
    assert "Fan-in, size" not in js


def test_universe_js_tooltip_uses_importers():
    js = _read("universe.js")
    # Tooltip strings use "importers:" not "fan-in"
    assert "importers:" in js
    # Tooltip template literals must not use "fan-in"
    assert "fan-in ${" not in js   # template literals in tooltip/label strings


def test_billing_js_uses_canonical_names():
    js = _read("billing.js")
    assert '"Change Plans"' in js
    assert '"Debug"' in js
    assert '"What Breaks"' in js
    assert '"Build plans"' not in js
    assert '"Investigations"' not in js
    assert '"Impact analyses"' not in js


# ── Task 3: Support / deployment model ───────────────────────────────────────

def test_support_installer_and_source_guidance_split():
    html = _read("support.html")
    assert "No Python required (installer)" in html
    assert "App won" in html and "(installer)" in html
    assert "App won" in html and "(source" in html
    assert "Generate your first Change Plan" in html
    assert "Rescan saved repository" in html


def test_quickstart_both_modes_documented():
    html = _read("quickstart.html")
    assert "No Python required" in html
    assert "Source mode" in html or "Python 3" in html


# ── Task 6: First user path ──────────────────────────────────────────────────

def test_first_user_path_no_dead_ends():
    """Home → Load Sample → Change Plan → Copy for Claude path has no dead ends."""
    home = _read("index.html")
    # Step 1: Load Sample button exists
    assert "Load Sample Repository" in home or "loadDemoMode" in home
    # Step 2: Change Plan tab exists and is reachable
    assert "go('build')" in home or "data-view=\"build\"" in home
    # Step 3: Generate Change Plan button
    assert "Generate Change Plan" in home
    # Step 4: Copy for Claude button
    assert "Copy for Claude" in home or "copyExport" in home

