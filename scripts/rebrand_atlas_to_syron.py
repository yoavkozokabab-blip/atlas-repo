"""Atlas -> Syron brand migration (branding only; no behavior change).

Word-boundary replacement so only standalone brand tokens change. Internal
identifiers are preserved automatically because `_`, `:` and adjacent letters are
word characters: `atlas_knowledge`, `atlas_self`, `atlas_beta`,
`atlas_recent_repos` (localStorage), `showAboutAtlas` and `atlas://…` never match.

Run:  py -3 scripts/rebrand_atlas_to_syron.py [--apply]
Without --apply it is a dry run (prints the change counts only).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "jarvis_desktop"

# Ordered replacements. Compound first, then word-boundary brand tokens.
_SUBS = [
    (re.compile(r"AtlasDesktop"), "SyronDesktop"),
    (re.compile(r"\bATLAS\b"), "SYRON"),
    (re.compile(r"\bAtlas\b"), "Syron"),
    (re.compile(r"\batlas\b"), "syron"),
]

# Curated target set: UI + user-facing code strings + brand tests. NOT
# atlas_knowledge (internal package + atlas:// data), NOT external_repos, NOT
# historical reports.
CODE_TARGETS = [
    DESKTOP / "server.py",
    DESKTOP / "api.py",
    DESKTOP / "planning_engine.py",
    DESKTOP / "domain_knowledge.py",
    DESKTOP / "reliability.py",
    DESKTOP / "impact_engine" / "concept_lexicon.py",
    DESKTOP / "impact_engine" / "__init__.py",
    DESKTOP / "architecture" / "__init__.py",
    DESKTOP / "evidence_engine" / "evidence_builder.py",
]
TEST_TARGETS = [
    DESKTOP / "tests" / "test_phase119_atlas_product_polish.py",
    DESKTOP / "tests" / "test_phase118b_landing_link_routing.py",
    DESKTOP / "tests" / "test_phase122_product_hardening.py",
    DESKTOP / "tests" / "test_phase110_first_user_demo_readiness.py",
    DESKTOP / "tests" / "test_phase141_private_beta_launch.py",
]

# User-facing brand strings in the billing/usage surface (plan taglines, dashboard
# labels, "Syron compute units"). Env vars like ATLAS_ADMIN are underscore-joined
# and so are preserved by the word boundaries. test_phase127/128 are intentionally
# NOT included: they reference the excluded atlas:// knowledge data.
def _billing_usage_targets() -> list[Path]:
    out: list[Path] = []
    for sub in ("billing", "usage"):
        out.extend(sorted((DESKTOP / sub).glob("*.py")))
    return out


def _static_targets() -> list[Path]:
    out: list[Path] = []
    static = DESKTOP / "static"
    for ext in ("*.html", "*.js", "*.css"):
        out.extend(sorted(static.glob(ext)))
    return out


def targets() -> list[Path]:
    seen: list[Path] = []
    for p in _static_targets() + CODE_TARGETS + TEST_TARGETS + _billing_usage_targets():
        if p.is_file() and p not in seen:
            seen.append(p)
    return seen


def rewrite(text: str) -> tuple[str, int]:
    count = 0
    for rx, repl in _SUBS:
        text, n = rx.subn(repl, text)
        count += n
    return text, count


def main(apply: bool) -> int:
    total = 0
    changed_files = 0
    rows = []
    for p in targets():
        try:
            original = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, n = rewrite(original)
        if n:
            rows.append((str(p.relative_to(ROOT)).replace("\\", "/"), n))
            total += n
            changed_files += 1
            if apply and new != original:
                p.write_text(new, encoding="utf-8")
    rows.sort(key=lambda r: -r[1])
    for rel, n in rows:
        print(f"{n:5}  {rel}")
    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total} replacements across "
          f"{changed_files} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv[1:]))
