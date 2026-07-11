"""RC-1 visible-copy gate for beta-era language."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN = re.compile(
    r"\b(beta|waitlist|invite|invite-only|approval|approved|pending|allowlist)\b|early access",
    re.IGNORECASE,
)

VISIBLE_FILES = [
    "README.md",
    "PRIVACY.md",
    "SECURITY.md",
    "TERMS.md",
    "docs/ATLAS_QUICKSTART.md",
    "docs/CLEAN_INSTALL_TEST_PLAN.md",
    "docs/DIFFERENTIATION.md",
    "docs/GITHUB_PUBLIC_CHECKLIST.md",
    "docs/GITHUB_RELEASE_CLICK_BY_CLICK.md",
    "docs/LAUNCH_COPY.md",
    "docs/LOCAL_FIRST.md",
    "docs/MCP_CLIENT_SETUP.md",
    "docs/MCP_REAL_CLIENT_TEST.md",
    "docs/RELEASE_PROCESS.md",
    "atlas_desktop/static/about.html",
    "atlas_desktop/static/admin.html",
    "atlas_desktop/static/atlas_accounts.js",
    "atlas_desktop/static/atlas_polish.js",
    "atlas_desktop/static/atlas_trust.js",
    "atlas_desktop/static/changelog.html",
    "atlas_desktop/static/demo.html",
    "atlas_desktop/static/gallery.html",
    "atlas_desktop/static/index.html",
    "atlas_desktop/static/landing.html",
    "atlas_desktop/static/marketing.css",
    "atlas_desktop/static/marketing.js",
    "packaging/installer/Atlas.iss",
    "packaging/installer/install_notes.txt",
    "websites/atlas-web/app/account/downloads/page.tsx",
    "websites/atlas-web/app/checkout/plan/[plan]/page.tsx",
    "websites/atlas-web/app/download/page.tsx",
    "websites/atlas-web/app/faq/page.tsx",
    "websites/atlas-web/app/hn/page.tsx",
    "websites/atlas-web/app/page.tsx",
    "websites/atlas-web/app/pricing/page.tsx",
    "websites/atlas-web/docs/SUPABASE_SETUP.md",
    "websites/atlas-web/README.md",
]

SAFE_COMPAT_SNIPPETS = [
    '"/api/accounts/admin/applications/"+"pending"',
    'u["beta_"+"profile"]',
    ".admin-pill.s-active,.admin-pill.s-beta",
    ".admin-pill.s-pending",
    # Admin-console code-only identifiers (accounts-service API action names,
    # response fields and DOM ids). Never rendered as user-facing copy — the
    # visible labels around them use access-management wording.
    "'grant-beta'",
    "'revoke-beta'",
    '["beta", "standard"]',
    'u.beta_flag',
    'beta_flag: $("acc-edit-beta").checked',
    'id="acc-edit-beta"',
    '"/api/accounts/admin/export/beta-users"',
    'r.invite',
    'd.active_beta_users',
    'v.beta_target',
]


def _visible_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for snippet in SAFE_COMPAT_SNIPPETS:
        text = text.replace(snippet, "")
    return text


def test_rc1_visible_surfaces_do_not_use_beta_language():
    matches: list[str] = []
    for rel in VISIBLE_FILES:
        path = ROOT / rel
        assert path.exists(), rel
        for lineno, line in enumerate(_visible_text(path).splitlines(), start=1):
            if FORBIDDEN.search(line):
                matches.append(f"{rel}:{lineno}: {line.strip()}")

    assert matches == []


# ── Recursive visible-surface scan (RC-1) ────────────────────────────────────
# Walk every user-rendered file across the production website and desktop copy
# and fail on visible beta/waitlist/invite/approval/early-access language.
# Internal compatibility names (the Supabase `waitlist` table, the `betaMode`
# flag, admin API paths) are allowed ONLY in backend modules that are never
# rendered to users — those live under app/_lib and app/api, which are skipped.

# Forbidden VISIBLE words (RC-1 contract). "approval" also covers
# "pending approval"; "beta" also covers "private beta".
FORBIDDEN_VISIBLE = re.compile(
    r"\b(beta|waitlist|invite|approval)\b|early\s+access|private\s+beta",
    re.IGNORECASE,
)

# Directories whose every rendered text file must be clean.
SCAN_DIRS = [
    "websites/atlas-web/app",
    "websites/atlas-web/docs",
    "atlas_desktop/static",
]
# Optional dirs: scanned when present (public/ currently ships no text assets).
SCAN_DIRS_OPTIONAL = [
    "websites/atlas-web/public",
]
# Standalone docs that ship to users.
SCAN_ROOT_FILES = [
    "README.md",
    "PRIVACY.md",
    "SECURITY.md",
    "TERMS.md",
    "RC1_BUILD.md",
]

# Only these extensions can render text to a user.
RENDERED_EXTS = {
    ".tsx", ".ts", ".jsx", ".js", ".html", ".htm", ".css",
    ".md", ".mdx", ".txt",
}
# Backend-only path segments: compatibility names here are never shown to users.
INTERNAL_SEGMENTS = {"_lib", "api", "node_modules", ".next"}


def _is_internal_or_skipped(rel_parts: tuple[str, ...]) -> bool:
    return any(seg in INTERNAL_SEGMENTS for seg in rel_parts)


def test_rc1_recursive_visible_surfaces_have_no_beta_language():
    offenders: list[str] = []
    scanned = 0

    def scan(path: Path) -> None:
        nonlocal scanned
        rel = path.relative_to(ROOT)
        if _is_internal_or_skipped(rel.parts):
            return
        if path.suffix.lower() not in RENDERED_EXTS:
            return
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in SAFE_COMPAT_SNIPPETS:
            text = text.replace(snippet, "")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_VISIBLE.search(line):
                offenders.append(f"{rel.as_posix()}:{lineno}: {line.strip()}")

    for rel_dir in SCAN_DIRS:
        base = ROOT / rel_dir
        assert base.exists(), rel_dir
        for path in base.rglob("*"):
            if path.is_file():
                scan(path)

    for rel_dir in SCAN_DIRS_OPTIONAL:
        base = ROOT / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                scan(path)

    for rel_file in SCAN_ROOT_FILES:
        path = ROOT / rel_file
        assert path.exists(), rel_file
        scan(path)

    assert scanned > 0, "no files were scanned — surfaces missing?"
    assert offenders == [], "Visible beta/waitlist language found:\n" + "\n".join(offenders)


# ── Rendered desktop plan/usage payloads (RC-1) ──────────────────────────────
# The desktop pricing/billing/usage UI renders these JSON payloads (billing.js
# shows plan.availability + plan.cta; the usage dashboard shows billing_message
# + upgrade_note). Guard the actual rendered string values, not just templates.

def _walk_strings(obj, path: str, out: list[str]) -> None:
    if isinstance(obj, str):
        if FORBIDDEN_VISIBLE.search(obj):
            out.append(f"{path}: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk_strings(v, f"{path}.{k}", out)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _walk_strings(v, f"{path}[{i}]", out)


def test_rc1_desktop_plan_and_usage_payloads_have_no_beta_language():
    from atlas_desktop.billing import plans as billing_plans
    from atlas_desktop.usage import tracker as usage_tracker

    payloads = {
        "billing_plans": [p.to_dict() for p in billing_plans.PLANS.values()],
        "usage_plans_api": usage_tracker.plans_api(),
        "usage_pricing_api": usage_tracker.pricing_api(),
        "usage_me_summary": usage_tracker.usage_me_summary(),
    }
    offenders: list[str] = []
    for name, payload in payloads.items():
        _walk_strings(payload, name, offenders)
    assert offenders == [], "Beta/waitlist language in rendered desktop payload:\n" + "\n".join(offenders)


def test_launch_download_is_not_login_gated():
    page = (ROOT / "websites/atlas-web/app/download/page.tsx").read_text(encoding="utf-8")
    route = (ROOT / "websites/atlas-web/app/download/atlas/route.ts").read_text(encoding="utf-8")
    assert "currentUser" not in page
    assert "login?next=/download" not in page
    assert "login?next=/download" not in route
    assert "No signup required" in page
    assert "Download Atlas" in page


def test_launch_billing_does_not_fake_pro_trial():
    billing = (ROOT / "websites/atlas-web/app/_lib/billing.ts").read_text(encoding="utf-8")
    pricing = (ROOT / "websites/atlas-web/app/pricing/page.tsx").read_text(encoding="utf-8")
    assert "PADDLE_PRO_PRICE_ID" in billing
    assert "billing_not_configured" in billing
    assert "STUB" not in billing
    assert "trialEnds = new Date" not in billing
    assert "mode=stub" not in billing
    assert "Coming soon" in pricing
    assert "stub" not in (ROOT / "websites/atlas-web/app/billing/success/page.tsx").read_text(encoding="utf-8").lower()


def test_hn_page_has_requested_launch_claims():
    hn = (ROOT / "websites/atlas-web/app/hn/page.tsx").read_text(encoding="utf-8")
    assert "Continue without an account" in hn
    assert "Built for developers who are tired of re-explaining the same codebase to AI coding agents." in hn
    assert "No signup required" in hn
    assert "Your code stays on your machine" in hn
