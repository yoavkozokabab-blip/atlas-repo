"""Phase 144A — restore the product brand Syron -> Atlas (branding only).

Exact inverse of scripts/rebrand_atlas_to_syron.py. Reuses that script's curated
target set so the revert is symmetric, and uses the same word-boundary technique
so internal identifiers stay untouched: because the Atlas->Syron migration never
created any `syron_*` identifier (every `atlas_knowledge`, `atlas_self`,
`atlas_recent_repos`, `ATLAS_*` env var and `atlas://` URI was preserved), the
only `Syron`/`SYRON`/`syron` tokens in the tree are user-facing brand words.

Run:  py -3 scripts/restore_atlas_brand.py [--apply]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rebrand_atlas_to_syron import ROOT, targets  # same curated file set

_SUBS = [
    (re.compile(r"SyronDesktop"), "AtlasDesktop"),
    (re.compile(r"\bSYRON\b"), "ATLAS"),
    (re.compile(r"\bSyron\b"), "Atlas"),
    (re.compile(r"\bsyron\b"), "atlas"),
]


def rewrite(text: str) -> tuple[str, int]:
    count = 0
    for rx, repl in _SUBS:
        text, n = rx.subn(repl, text)
        count += n
    return text, count


def main(apply: bool) -> int:
    total = 0
    changed = 0
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
            changed += 1
            if apply and new != original:
                p.write_text(new, encoding="utf-8")
    rows.sort(key=lambda r: -r[1])
    for rel, n in rows:
        print(f"{n:5}  {rel}")
    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total} replacements across {changed} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv[1:]))
