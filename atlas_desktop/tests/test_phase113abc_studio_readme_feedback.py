"""Phase 113A/B/C — demo studio, GitHub showcase README, feedback collection."""

from __future__ import annotations

import os

from atlas_desktop import api, server

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def _s(name):  # read a static file
    with open(os.path.join(STATIC, name), "r", encoding="utf-8") as fh:
        return fh.read()


# ---------- 113A: Demo Studio (recording mode) ----------
def test_studio_files_exist():
    assert os.path.getsize(os.path.join(STATIC, "studio.html")) > 800
    assert os.path.getsize(os.path.join(STATIC, "studio.js")) > 1500


def test_studio_is_cinematic_recording_mode():
    html, js = _s("studio.html"), _s("studio.js")
    assert "Start Demo" in html               # one-click start
    assert "brandmark" in html                # clean branding
    assert "3d-force-graph" in html           # maximized 3D graph
    assert "overflow:hidden" in html          # full-bleed, no chrome
    # scripted flow: graph → risk → impact → copilot → export
    for scene in ("universe", "risk", "impact", "copilot", "export", "outro"):
        assert scene in js, f"studio missing scene: {scene}"
    for fn in ("startDemo", "runSequence", "startOrbit", "restartDemo"):
        assert fn in js
    assert "/api/demo/load" in js             # loads a demo repo hands-free


def test_demo_load_api_supports_studio():
    # the studio relies on the demo-load + graph/risks/summary/export endpoints
    assert api.list_demo_packs().get("ok")
    loaded = api.load_demo_mode("small")
    assert loaded.get("ok")
    assert api.current_graph().get("ok")
    assert api.current_risks().get("ok")
    assert api.context_export("claude", "compact").get("ok")


# ---------- 113B: GitHub showcase README ----------
def test_showcase_readme_retired():
    # RC-1 rebrand: the legacy JARVIS-era showcase README is gone; README.md is
    # the single product doc (asserted below).
    assert not os.path.isfile(os.path.join(ROOT, "README_JARVIS.md"))


def test_root_readme_is_the_atlas_product_doc():
    # RC-1: the root README is the Atlas product doc (the old personal-assistant
    # README is gone with the legacy codebase).
    root = open(os.path.join(ROOT, "README.md"), "r", encoding="utf-8").read()
    assert root.lstrip().startswith("# Atlas")
    assert "jarvis" not in root.lower()


# ---------- 113C: Feedback collection ----------
def test_feedback_widget_has_required_categories_and_storage():
    js = _s("feedback.js")
    for cat in ("Bug", "Confusing UI", "Missing feature", "General feedback"):
        assert cat in js, f"feedback missing category: {cat}"
    assert "localStorage" in js and "atlas_feedback" in js     # store locally
    assert "exportJSON" in js                                   # export all as JSON
    assert "AtlasFeedback" in js                                # public API
    assert "fb-btn" in js                                       # self-injecting button


def test_feedback_page_lists_and_exports():
    html = _s("feedback.html")
    assert "Feedback inbox" in html or "feedback" in html.lower()
    assert "exportJSON" in html and "feedback.js" in html


def test_feedback_widget_wired_into_marketing_pages():
    # beta.html was deleted with the beta-era pages (RC-1 open access).
    for page in ("landing.html", "demo.html", "gallery.html"):
        assert "feedback.js" in _s(page), f"{page} does not include the feedback widget"


# ---------- serving ----------
def test_server_serves_new_pages():
    for f in ("studio.html", "studio.js", "feedback.html", "feedback.js"):
        assert os.path.isfile(os.path.join(server.STATIC_DIR, f))
