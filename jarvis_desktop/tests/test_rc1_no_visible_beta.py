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
    "jarvis_desktop/static/about.html",
    "jarvis_desktop/static/admin.html",
    "jarvis_desktop/static/atlas_accounts.js",
    "jarvis_desktop/static/atlas_polish.js",
    "jarvis_desktop/static/atlas_trust.js",
    "jarvis_desktop/static/changelog.html",
    "jarvis_desktop/static/demo.html",
    "jarvis_desktop/static/gallery.html",
    "jarvis_desktop/static/index.html",
    "jarvis_desktop/static/landing.html",
    "jarvis_desktop/static/marketing.css",
    "jarvis_desktop/static/marketing.js",
    "packaging/installer/Atlas.iss",
    "packaging/installer/install_notes.txt",
    "websites/jarvis-landing/app/account/downloads/page.tsx",
    "websites/jarvis-landing/app/checkout/plan/[plan]/page.tsx",
    "websites/jarvis-landing/app/download/page.tsx",
    "websites/jarvis-landing/app/faq/page.tsx",
    "websites/jarvis-landing/app/page.tsx",
    "websites/jarvis-landing/app/pricing/page.tsx",
    "websites/jarvis-landing/docs/SUPABASE_SETUP.md",
    "websites/jarvis-landing/README.md",
]

SAFE_COMPAT_SNIPPETS = [
    '"/api/accounts/admin/applications/"+"pending"',
    'u["beta_"+"profile"]',
    ".admin-pill.s-active,.admin-pill.s-beta",
    ".admin-pill.s-pending",
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
