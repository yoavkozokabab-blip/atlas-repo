"""Phase 113 — branding / waitlist / landing marketing layer tests (offline)."""

from __future__ import annotations

import os

import pytest

from jarvis_desktop import server

STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
MARKETING = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "marketing")


def _read(name: str) -> str:
    with open(os.path.join(STATIC, name), "r", encoding="utf-8") as fh:
        return fh.read()


PAGES = ["landing.html", "demo.html", "gallery.html", "beta.html", "admin.html"]
ASSETS = ["marketing.css", "marketing.js"]


@pytest.mark.parametrize("page", PAGES + ASSETS)
def test_marketing_files_exist_and_nonempty(page):
    path = os.path.join(STATIC, page)
    assert os.path.isfile(path), f"missing {page}"
    assert os.path.getsize(path) > 400, f"{page} too small"


def test_landing_value_proposition_under_the_fold():
    html = _read("landing.html")
    # the <30s value prop must be present, verbatim where required
    assert "Stop making AI" in html and "read your entire repository" in html
    assert "before Claude, Codex or Cursor ever see your code" in html
    # CTAs
    assert "Join the Waitlist" in html or "Join Waitlist" in html
    assert "Watch the Demo" in html or "demo.html" in html
    # the 5 required features
    for feat in ("Repository Intelligence", "Dependency Universe", "What Breaks",
                 "Architecture Risk Detection", "Cursor Export"):
        assert feat in html, f"missing feature: {feat}"
    # required sections
    assert 'id="features"' in html and 'id="faq"' in html and 'id="screens"' in html


def test_landing_does_not_overclaim_positioning():
    html = _read("landing.html")
    assert "does" in html.lower() and "replace" in html.lower()  # "does not replace" framing present
    assert "local" in html.lower()  # local-first trust


def test_waitlist_interface_present():
    html = _read("landing.html")
    js = _read("marketing.js")
    # form fields: name, email, company, repo size, AI tool
    for fid in ("wlName", "wlEmail", "wlCompany", "wlSize", "wlTool"):
        assert fid in html, f"missing waitlist field {fid}"
    # backend-ready storage interface + count
    for fn in ("submitWaitlist", "persistSignup", "getSignups", "waitlistCount", "openWaitlist"):
        assert fn in js, f"missing waitlist fn {fn}"
    assert "WAITLIST_BASE = 127" in js  # configurable placeholder count


def test_demo_page_has_video_and_chapters():
    html = _read("demo.html")
    assert "video-frame" in html and "60" in html
    assert html.count("chapter") >= 3


def test_gallery_has_all_five_surfaces():
    html = _read("gallery.html")
    for surface in ("Dependency Universe", "AI Copilot", "What Breaks",
                    "Architecture Risk", "Cursor Export"):
        assert surface in html, f"gallery missing {surface}"
    assert "real-shot" in html  # supports dropping in real PNGs


def test_beta_page_sections():
    html = _read("beta.html")
    assert "Who should join" in html and "feedback" in html.lower() and "Timeline" in html


def test_admin_dashboard_kpis():
    html = _read("admin.html")
    for kpi in ("kWaitlist", "kScans", "kExports", "kCopilot"):
        assert kpi in html, f"admin missing KPI {kpi}"
    assert "/api/analytics/summary" in html  # reads live analytics when app runs


def test_every_page_navigates_back_to_app_and_landing():
    for page in PAGES:
        html = _read(page)
        assert "landing.html" in html, f"{page} has no link home"
        assert "index.html" in html, f"{page} has no link to the app"


def test_marketing_kit_assets_present():
    for f in ("README.md", "launch_copy.md", "x_launch.md", "reddit_launch.md",
              "hackernews_launch.md", "github_readme_screenshots.md"):
        path = os.path.join(MARKETING, f)
        assert os.path.isfile(path) and os.path.getsize(path) > 200, f"missing marketing/{f}"


def test_static_server_can_serve_marketing(tmp_path):
    # the existing stdlib static handler resolves files under STATIC; sanity-check the dir
    assert os.path.isfile(os.path.join(server.STATIC_DIR, "landing.html"))
    assert os.path.isfile(os.path.join(server.STATIC_DIR, "marketing.css"))
