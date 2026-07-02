"""Phase 193B — Home experience & navigation simplification.

Static contract for the onboarding home dashboard, the simplified primary
navigation, the restructured user menu, and the polished status dashboards.
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
INDEX = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "styles.css").read_text(encoding="utf-8")
ACCOUNTS_JS = (STATIC / "atlas_accounts.js").read_text(encoding="utf-8")


def _nav_block() -> str:
    start = INDEX.find('<nav class="nav"')
    end = INDEX.find("</nav>", start)
    assert start >= 0 and end >= 0
    return INDEX[start:end]


# ── Part 1 — Real home page (onboarding dashboard) ───────────────────────────
def test_home_has_welcome_and_tagline():
    assert 'id="homeWelcome"' in INDEX
    assert "class=\"home-tagline\"" in INDEX
    assert "understand large repositories before your AI starts changing code" in INDEX


def test_home_has_large_quick_action_cards():
    cards = INDEX[INDEX.find('class="quick-action-cards"'):]
    cards = cards[: cards.find("</section>")]
    # RC-1 copy: sharpened card titles (Debug Issue -> Find bug root cause,
    # What Breaks? -> Impact analysis).
    for title in ("Scan Repository", "Find bug root cause", "Change Plan", "Impact analysis"):
        assert title in cards, title
    for desc in (
        "Choose a repository and build understanding.",
        "Investigate bugs and root causes.",
        "Plan a code change before implementation.",
        "See what breaks before you edit.",
    ):
        assert desc in cards, desc
    assert "qa-card" in CSS


def test_home_has_getting_started_that_can_autohide():
    assert 'id="homeGettingStarted"' in INDEX
    gs = INDEX[INDEX.find('id="homeGettingStarted"'):]
    gs = gs[: gs.find("</section>")]
    # RC-1 getting-started steps follow the real first-run journey.
    for step in ("Scan a local repository", "Connect Cursor or Claude", "Ask a repo-aware question", "Build a Change Plan"):
        assert step in gs, step
    # Auto-hides once usage history exists.
    assert "homeGettingStarted" in ACCOUNTS_JS
    assert "gs.style.display = items.length ? 'none' : ''" in ACCOUNTS_JS


def test_home_recent_activity_three_columns_with_empty_states():
    assert 'id="homeRecentAnalyses"' in INDEX
    assert 'id="homeRecentRepos"' in INDEX
    assert 'id="homeRecentExports"' in INDEX
    for empty in ("No analyses yet", "No repositories yet", "No exports yet"):
        assert empty in INDEX, empty


# ── Part 2 — Account removed from main navigation ────────────────────────────
def test_primary_nav_has_only_core_workflows():
    nav = _nav_block()
    assert "Account" not in nav
    assert 'data-view="accounts"' not in nav
    for view in ("home", "scan", "center", "build", "investigate", "impact"):
        assert f'data-view="{view}"' in nav, view


# ── Part 3 — User menu restructure ───────────────────────────────────────────
def test_user_menu_contains_account_devices_admin_signout():
    menu = INDEX[INDEX.find('id="userMenu"'):]
    menu = menu[: menu.find("</details>")]
    assert "Account" in menu
    assert ">Devices<" in menu
    assert "atlasAccounts.openDevices()" in menu
    assert 'id="userMenuAdmin"' in menu and "Admin Workspace" in menu
    assert "Support" in menu
    assert "Sign out" in menu
    # Admin Workspace stays role-gated.
    assert 'class="btn ghost small admin-only" id="userMenuAdmin"' in INDEX
    assert "openDevices: openDevices" in ACCOUNTS_JS


# ── Parts 4-6 — Status dashboard tone + copy ─────────────────────────────────
def test_pending_dashboard_removed_with_open_access():
    # RC-1 open self-serve: there is no application/queue state any more, so
    # the "pending" status dashboard must be gone entirely.
    assert "pending: {" not in ACCOUNTS_JS
    assert "submitted successfully" not in ACCOUNTS_JS


def test_inactive_dashboard_is_neutral_not_warning():
    spec = ACCOUNTS_JS[ACCOUNTS_JS.find("inactive: {"):]
    spec = spec[: spec.find("};")]
    assert "tone: 'neutral'" in spec
    assert "signed in" in spec.lower()
    assert "account exists" in spec.lower()
    # No alarming language in the user-facing copy (ignore code comments).
    copy = "\n".join(ln for ln in spec.splitlines() if "//" not in ln)
    assert not re.search(r"error|failed|denied", copy, re.IGNORECASE)


def test_rejected_dashboard_removed_with_open_access():
    # RC-1 open self-serve: no rejection state, no re-apply flow.
    assert "rejected: {" not in ACCOUNTS_JS
    assert "showReapply: true" not in ACCOUNTS_JS


# ── Part 8 — UX cleanup: single status indicator on home ─────────────────────
def test_home_has_single_status_indicator():
    # Exactly one status pill on the home dashboard (no duplicate plan badge).
    dash = INDEX[INDEX.find('id="homeDashboard"'):]
    dash = dash[: dash.find('<div class="hero">')]
    assert dash.count('class="status-pill"') == 1
    assert 'id="homePlanPill"' not in INDEX
    # Status + plan are combined into the one pill.
    assert "s.label + ' · ' + planTitle" in ACCOUNTS_JS
