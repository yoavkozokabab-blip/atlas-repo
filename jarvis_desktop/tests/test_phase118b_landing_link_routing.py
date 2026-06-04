"""Phase 118B landing-page routing audit."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


STATIC = Path(__file__).resolve().parents[1] / "static"
LANDING = STATIC / "landing.html"
STATIC_PAGES = {
    "privacy.html": "Privacy Policy",
    "terms.html": "Terms of Service",
    "security.html": "Security",
    "about.html": "About",
    "contact.html": "Contact",
    "roadmap.html": "Roadmap",
    "changelog.html": "Changelog",
    "docs.html": "Documentation",
}
REQUIRED_ANCHORS = {"product", "repositories", "features", "beta", "faq", "waitlist"}
MARKETING_PAGES = [
    "landing.html",
    "demo.html",
    "gallery.html",
    "beta.html",
    *STATIC_PAGES,
]


class _MarkupAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[dict[str, str]] = []
        self.buttons: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a":
            self.links.append(values)
        if tag == "button":
            self.buttons.append(values)


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _parse(name: str) -> _MarkupAudit:
    parser = _MarkupAudit()
    parser.feed(_read(name))
    return parser


def test_landing_internal_navigation_targets_exist() -> None:
    page = _parse("landing.html")
    assert REQUIRED_ANCHORS <= page.ids
    for link in page.links:
        href = link.get("href", "")
        if href.startswith("#") and href != "#":
            assert href[1:] in page.ids, f"landing.html has missing target: {href}"


def test_required_footer_routes_are_present() -> None:
    html = _read("landing.html")
    for href in (
        "#product",
        "#repositories",
        "#features",
        "#beta",
        "#faq",
        "#waitlist",
        *STATIC_PAGES,
    ):
        assert f'href="{href}"' in html, f"landing footer is missing {href}"


def test_marketing_pages_have_no_silent_home_links() -> None:
    for name in MARKETING_PAGES:
        for link in _parse(name).links:
            if link.get("href") == "#":
                assert "openWaitlist" in link.get("onclick", ""), (
                    f"{name} has a bare href='#' without an explicit action"
                )


def test_static_information_pages_are_atlas_branded_and_navigate_home() -> None:
    for name, title in STATIC_PAGES.items():
        html = _read(name)
        assert "<title>" + title in html
        assert "ATLAS" in html
        assert 'href="landing.html"' in html or 'href="landing.html#waitlist"' in html


def test_marketing_relative_html_destinations_exist() -> None:
    for name in MARKETING_PAGES:
        for link in _parse(name).links:
            href = link.get("href", "")
            destination = href.split("#", 1)[0]
            if destination.endswith(".html"):
                assert (STATIC / destination).is_file(), f"{name} links to missing {destination}"


def test_legal_pages_do_not_claim_final_legal_completeness() -> None:
    assert "not a substitute for a final legal policy" in _read("privacy.html")
    assert "not a complete production terms document" in _read("terms.html")
    assert "without claiming a completed security certification" in _read("security.html")


def test_unconfigured_social_links_use_visible_coming_soon_behavior() -> None:
    html = _read("landing.html")
    js = _read("marketing.js")
    for social in ("github", "x", "discord"):
        assert f"openAtlasSocial('{social}')" in html
        assert f'{social}: ""' in js
    assert "const ATLAS_LINKS" in js
    assert "Coming soon — official Atlas link not configured yet." in js
    assert "openAtlasSocial" in js


def test_hash_navigation_updates_same_page_without_top_jump() -> None:
    js = _read("marketing.js")
    assert "initHashNavigation" in js
    assert 'if (!hash || hash === "#") return;' in js
    assert "scrollIntoView" in js
    assert "history.replaceState" in js
